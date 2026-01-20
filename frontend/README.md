# Frontend README

## Setup

### 1. Install dependencies
```bash
npm install
```

### 2. Configure environment
```bash
cp .env.example .env.local
# Edit .env.local if needed
```

### 3. Run development server
```bash
npm run dev
```

### 4. Build for production
```bash
npm run build
```

### 5. Preview production build
```bash
npm run preview
```

## Project Structure

```
frontend/
├── src/
│   ├── api/              # API client & hooks
│   ├── components/       # Reusable components
│   ├── pages/            # Page components
│   ├── contexts/         # React contexts
│   ├── hooks/            # Custom hooks
│   ├── utils/            # Utility functions
│   ├── styles/           # Global styles
│   ├── types/            # TypeScript types
│   ├── App.tsx           # Root component
│   ├── main.tsx          # Entry point
│   └── index.css         # Global CSS
├── public/               # Static assets
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint

## Technologies

- React 18
- TypeScript
- Vite
- Tailwind CSS
- React Router
- TanStack Query
- React Leaflet
- Axios
