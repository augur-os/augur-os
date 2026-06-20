// Mock Google Fonts CSS responses for offline builds.
// Set NEXT_FONT_GOOGLE_MOCKED_RESPONSES to this file path.
module.exports = new Proxy(
  {},
  {
    get: () => "/* mocked font css */",
  },
);
