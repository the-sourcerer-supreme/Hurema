const { defineConfig } = require("vite");
const path = require("path");

module.exports = defineConfig({
  root: path.resolve(__dirname, "frontend"),
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
