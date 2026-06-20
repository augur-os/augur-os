export const AUGUR_BRIDGE_SHIM = `<script>
/* window.augur bridge — exposes only ask + runAction over postMessage */
(function () {
  function post(msg) { try { window.parent.postMessage(msg, "*"); } catch (e) {} }
  Object.defineProperty(window, "augur", {
    value: Object.freeze({
      ask: function (prompt) { post({ type: "augur:ask", prompt: String(prompt == null ? "" : prompt) }); },
      runAction: function (actionId) { post({ type: "augur:runAction", actionId: String(actionId == null ? "" : actionId) }); }
    }),
    writable: false, configurable: false
  });
})();
</script>`;
export function injectAugurBridge(html: string): string {
  const idx = html.lastIndexOf("</body>");
  if (idx === -1) return `${html}\n${AUGUR_BRIDGE_SHIM}`;
  return `${html.slice(0, idx)}${AUGUR_BRIDGE_SHIM}\n${html.slice(idx)}`;
}
