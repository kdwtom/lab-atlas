import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// base './' so the static build works from any GitHub Pages sub-path (routing uses HashRouter).
export default defineConfig({
  base: './',
  plugins: [react()],
});
