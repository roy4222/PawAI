PawAI Studio frontend — Next.js app.

## Getting Started

**Canonical package manager is npm** — `package.json` pins `"packageManager": "npm@11.x"`,
and `.gitignore` blocks stray `pnpm-lock.yaml` / `yarn.lock` to keep the lockfile single-source.
Don't run `pnpm install` / `yarn install` here.

Easiest path: from repo root, run

```bash
pawai demo start
```

This auto-creates `.env.local` (with the Jetson Gateway URL), runs `npm install` if needed,
launches the dev server via `node_modules/.bin/next`, and prints the actual Studio URL.

Manual:

```bash
cp .env.local.example .env.local
$EDITOR .env.local      # set NEXT_PUBLIC_GATEWAY_HOST to your Jetson Tailscale IP
npm install
npm run dev             # or `./node_modules/.bin/next dev` to bypass any wrapper hooks
```

Open [http://localhost:3000/studio](http://localhost:3000/studio) (Studio entry, not `/`).
The page auto-updates as you edit files.

See [`docs/pawai_cli/`](../../docs/pawai_cli/) for the full toolchain and troubleshooting.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
