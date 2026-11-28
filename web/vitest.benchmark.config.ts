import { defineConfig } from 'vitest/config';
export default defineConfig({ test: { environment: 'node', include: ['tests/search/benchmark/**/*.test.ts'], testTimeout: 120000 } });
