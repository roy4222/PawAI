# Copyright (c) 2024, RoboVerse community
# SPDX-License-Identifier: BSD-3-Clause

import asyncio
import json
import logging
from typing import Callable, Dict, Any

from ...domain.interfaces import IRobotDataReceiver, IRobotController
from ...domain.entities import RobotData, RobotConfig
from .go2_connection import Go2Connection
from ...application.utils.command_generator import gen_command, gen_mov_command
from ...domain.constants import ROBOT_CMD, RTC_TOPIC, AUDIO_HUB_COMMANDS
from .go2_connection import ConnectionHealth

logger = logging.getLogger(__name__)


class WebRTCAdapter(IRobotDataReceiver, IRobotController):
    """WebRTC adapter for robot communication"""

    def __init__(self, config: RobotConfig, on_validated_callback: Callable, on_video_frame_callback: Callable = None, event_loop=None):
        self.config = config
        self.connections: Dict[str, Go2Connection] = {}
        self.data_callback: Callable[[RobotData], None] = None
        self.webrtc_msgs = asyncio.Queue()
        self.on_validated_callback = on_validated_callback
        self.on_video_frame_callback = on_video_frame_callback
        # Store the event loop (passed from main thread or detect current)
        if event_loop:
            self.main_loop = event_loop
        else:
            try:
                self.main_loop = asyncio.get_running_loop()
            except RuntimeError:
                self.main_loop = None

    async def connect(self, robot_id: str) -> None:
        """Connect to robot via WebRTC"""
        try:
            robot_idx = int(robot_id)
            robot_ip = self.config.robot_ip_list[robot_idx]
            
            conn = Go2Connection(
                robot_ip=robot_ip,
                robot_num=robot_id,
                token=self.config.token,
                on_validated=self._on_validated,
                on_message=self._on_data_channel_message,
                on_video_frame=self.on_video_frame_callback if self.config.enable_video else None,
                decode_lidar=self.config.decode_lidar,
                enable_audio_track=True,
            )
            
            self.connections[robot_id] = conn
            await conn.connect()
            await conn.disableTrafficSaving(True)
            
            logger.info(f"Connected to robot {robot_id} at {robot_ip}")
            
        except Exception as e:
            logger.error(f"Failed to connect to robot {robot_id}: {e}")
            raise

    async def disconnect(self, robot_id: str) -> None:
        """Disconnect from robot"""
        if robot_id in self.connections:
            try:
                # Используем правильный метод для закрытия WebRTC соединения
                connection = self.connections[robot_id]
                if hasattr(connection, 'disconnect'):
                    await connection.disconnect()
                elif hasattr(connection, 'pc') and connection.pc:
                    await connection.pc.close()
                del self.connections[robot_id]
                logger.info(f"Disconnected from robot {robot_id}")
            except Exception as e:
                logger.error(f"Error disconnecting from robot {robot_id}: {e}")

    async def ensure_connection(self, robot_id: str) -> bool:
        conn = self.connections.get(robot_id)
        if conn is None:
            logger.warning("No connection for robot %s, reconnecting", robot_id)
            await self.connect(robot_id)
            return True

        state = getattr(conn.pc, "connectionState", "unknown")
        if state in ("failed", "closed"):
            logger.warning(
                "Connection state %s for robot %s, reconnecting", state, robot_id
            )
            await self.disconnect(robot_id)
            await asyncio.sleep(0.5)
            await self.connect(robot_id)
            return True

        return False

    def set_data_callback(self, callback: Callable[[RobotData], None]) -> None:
        """Set callback for data reception"""
        self.data_callback = callback

    def send_command(self, robot_id: str, command: str) -> None:
        """Send command to robot"""
        if robot_id in self.connections:
            try:
                connection = self.connections[robot_id]
                if hasattr(connection, 'data_channel') and connection.data_channel:
                    # Use asyncio.run_coroutine_threadsafe to handle cross-thread calls
                    loop = self._get_or_create_event_loop()
                    if loop and loop.is_running():
                        # Schedule the coroutine in the existing loop
                        asyncio.run_coroutine_threadsafe(
                            self._async_send_command(connection, command),
                            loop
                        )
                    else:
                        # No running event loop — cannot safely send cross-thread
                        logger.error(
                            f"Cannot send command to {robot_id}: "
                            "asyncio event loop not running (cross-thread send is unsafe)"
                        )
                    logger.debug(f"Command sent to robot {robot_id}: {command[:50]}")
                else:
                    logger.warning(f"No data channel available for robot {robot_id}")
            except Exception as e:
                logger.error(f"Error sending command to robot {robot_id}: {e}")

    def _get_or_create_event_loop(self):
        """Get existing event loop or return the main loop"""
        # First try to get the current loop
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            # If no current loop, return the main loop stored during init
            return self.main_loop

    async def _async_send_command(self, connection, command: str):
        """Async wrapper for sending commands with observability"""
        try:
            if hasattr(connection, 'data_channel') and connection.data_channel:
                dc = connection.data_channel
                state = dc.readyState if hasattr(dc, 'readyState') else 'unknown'

                if state != "open":
                    logger.warning(f"[DC SEND] Cannot send: dc_state={state}")
                    return

                # Parse api_id for audio command logging
                _api = 0
                try:
                    _cmd = json.loads(command) if isinstance(command, str) else {}
                    _api = _cmd.get('data', {}).get('header', {}).get('identity', {}).get('api_id', 0)
                except (json.JSONDecodeError, AttributeError):
                    pass

                buffered_before = getattr(dc, 'bufferedAmount', None)
                dc.send(command)
                buffered_after = getattr(dc, 'bufferedAmount', None)

                # Detailed log for audio commands
                _audio_ids = set(AUDIO_HUB_COMMANDS.values())
                if _api in _audio_ids:
                    _payload_len = len(command) if isinstance(command, (bytes, str)) else "?"
                    logger.info(
                        f"[AUDIO DEBUG] dc_state={state} api_id={_api} "
                        f"payload_len={_payload_len} buffered={buffered_before}→{buffered_after}"
                    )

                # Buffer backlog alerts
                if buffered_after is not None:
                    if buffered_after > 512_000:
                        logger.error(f"[DC BUFFER] bufferedAmount={buffered_after} — CRITICAL backlog")
                    elif buffered_after > 64_000:
                        logger.warning(f"[DC BUFFER] bufferedAmount={buffered_after} — backlogged")
            else:
                logger.warning("[DC SEND] No data channel on connection!")
        except Exception as e:
            logger.error(f"Error in async send command: {e}")

    def send_movement_command(self, robot_id: str, x: float, y: float, z: float) -> None:
        """Send movement command to robot"""
        try:
            command = gen_mov_command(
                round(x, 2), 
                round(y, 2), 
                round(z, 2), 
                self.config.obstacle_avoidance
            )
            self.send_command(robot_id, command)
        except Exception as e:
            logger.error(f"Error sending movement command: {e}")

    def send_stand_up_command(self, robot_id: str) -> None:
        """Send stand up command"""
        try:
            stand_up_cmd = gen_command(ROBOT_CMD["StandUp"])
            self.send_command(robot_id, stand_up_cmd)
            
            move_cmd = gen_command(ROBOT_CMD['BalanceStand'])
            self.send_command(robot_id, move_cmd)
        except Exception as e:
            logger.error(f"Error sending stand up command: {e}")

    def send_stand_down_command(self, robot_id: str) -> None:
        """Send stand down command"""
        try:
            stand_down_cmd = gen_command(ROBOT_CMD["StandDown"])
            self.send_command(robot_id, stand_down_cmd)
        except Exception as e:
            logger.error(f"Error sending stand down command: {e}")

    def send_webrtc_request(self, robot_id: str, api_id: int, parameter: Any, topic: str) -> None:
        """Send WebRTC request directly (bypass queue for thread safety)"""
        try:
            payload = gen_command(api_id, parameter, topic)
            self.send_command(robot_id, payload)
            logger.debug(f"WebRTC request sent to robot {robot_id} (api_id={api_id})")
        except Exception as e:
            logger.error(f"Error sending WebRTC request: {e}")

    def process_webrtc_commands(self, robot_id: str) -> None:
        """Process WebRTC commands from queue"""
        while True:
            try:
                message = self.webrtc_msgs.get_nowait()
                try:
                    self.send_command(robot_id, message)
                finally:
                    self.webrtc_msgs.task_done()
            except asyncio.QueueEmpty:
                break

    def play_tts_audio(self, robot_id: str, wav_bytes: bytes) -> None:
        """Send TTS audio via WebRTC audio track (experimental)."""
        conn = self.connections.get(robot_id)
        if conn is None:
            logger.warning("[AUDIO TRACK] No connection for robot %s (keys=%s)", robot_id, list(self.connections.keys()))
            return
        tts_track = getattr(conn, '_tts_track', None)
        if tts_track is None:
            logger.warning("[AUDIO TRACK] Connection has no _tts_track for robot %s", robot_id)
            return

        loop = self._get_or_create_event_loop()
        if loop and loop.is_running():
            conn._tts_track.enqueue_audio_threadsafe(wav_bytes, loop)
            logger.info("[AUDIO TRACK] Enqueued TTS audio for robot %s", robot_id)
        else:
            logger.error("[AUDIO TRACK] No running event loop for audio playback")

    def get_connection_health(self, robot_id: str = "0"):
        """Get thread-safe health snapshot for a robot connection."""
        conn = self.connections.get(robot_id)
        if conn is None:
            return None
        return conn.health  # Returns a copy via @property

    def _on_validated(self, robot_id: str) -> None:
        """Callback after connection validation"""
        try:
            if robot_id in self.connections:
                subscription_topics = [
                    RTC_TOPIC["ROBOTODOM"],
                ]

                if not self.config.minimal_state_topics:
                    subscription_topics.extend(
                        [
                            RTC_TOPIC["LOW_STATE"],
                            RTC_TOPIC["LF_SPORT_MOD_STATE"],
                        ]
                    )

                if self.config.enable_lidar or self.config.decode_lidar or self.config.publish_raw_voxel:
                    subscription_topics.append(RTC_TOPIC["ULIDAR_ARRAY"])

                # Subscribe to audiohub player state for playback observability
                subscription_topics.append(RTC_TOPIC["AUDIO_HUB_PLAY_STATE"])

                for topic in subscription_topics:
                    self.connections[robot_id].data_channel.send(
                        json.dumps({"type": "subscribe", "topic": topic}))
            
            if self.on_validated_callback:
                self.on_validated_callback(robot_id)
                
        except Exception as e:
            logger.error(f"Error in validated callback: {e}")

    def _on_data_channel_message(self, _, msg: Dict[str, Any], robot_id: str) -> None:
        """Handle incoming data channel messages"""
        try:
            if self.data_callback:
                # Создаем объект RobotData для передачи в callback
                # Фактическая обработка будет в RobotDataService
                robot_data = RobotData(robot_id=robot_id, timestamp=0.0)
                self.data_callback(msg, robot_id)  # Передаем сырые данные для обработки
                
        except Exception as e:
            logger.error(f"Error processing data channel message: {e}") 
