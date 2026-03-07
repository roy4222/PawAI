# Face Dashboard FastAPI Backend

## Run

```bash
cd /home/jetson/elder_and_dog/face_dashboard_fastapi
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py --host 0.0.0.0 --port 8000
```

## Endpoints

- `GET /api/status`
- `GET /api/model/profiles`
- `POST /api/model/select`
- `GET /api/stream/health`
- `POST /api/enroll/start`
- `POST /api/enroll/stop`
- `POST /api/infer/start`
- `POST /api/infer/stop`

## Model Profile Switch

Select active profile:

```bash
curl -X POST http://127.0.0.1:8000/api/model/select \
  -H "Content-Type: application/json" \
  -d '{"profile_id":"yunet_sface_fp32"}'
```

List profiles:

```bash
curl http://127.0.0.1:8000/api/model/profiles
```
