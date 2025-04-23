import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import prism from "vite-plugin-prismjs";

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    prism({
      languages: [
        "javascript",
        "css",
        "markup",
        "typescript",
        "python",
        "go",
        "bash",
        "json",
        "c",
        "cpp",
        "jsx",
        "tsx",
        "scss",
        "less",
        "stylus",
        "rust",
        "solidity",
        "java",
        "ruby",
        "php",
        "sql",
        "markdown",
        "yaml",
        "toml",
        "docker",
        "git",
        "diff",
        "regex",
        "graphql",
        "protobuf",
      ],
      theme: "tomorrow",
      css: true,
    }),
  ],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:10000',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: '../app/static',  // Output to the app's static directory
    emptyOutDir: true,        // Clean the output directory before build
  },
});