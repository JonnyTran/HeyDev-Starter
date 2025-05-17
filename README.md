This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the frontend server:

```bash
# at repo root
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

Then, run the agent backend:

```bash
cd agent && poetry lock && poetry install && poetry run demo
```

fastapi server docs at [http://localhost:8000/docs](http://localhost:8000/docs)
