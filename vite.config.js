const { defineConfig } = require("vite");
const path = require("path");

module.exports = defineConfig({
  root: path.resolve(__dirname, "frontend"),
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
