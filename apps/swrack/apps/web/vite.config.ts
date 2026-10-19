// version 26
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { defineConfig } from 'vite';

export default defineConfig({
  // Mount path when served under a proxy prefix (e.g. /rack in SWSuite).
  // Defaults to '/', so a standalone build is unchanged.
  base: process.env.BASE_PATH || '/',
  plugins: [svelte()],
  publicDir: 'static',
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8080',
      '/assets': 'http://localhost:8080'
    }
  }
});
