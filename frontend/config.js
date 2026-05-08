// FE Copilot - backend URL configuration
// Automatically routes to AWS when accessed from any non-localhost origin.
// Local dev (localhost / 127.0.0.1 / 0.0.0.0) uses relative /api/v1 paths
// so FastAPI on port 8123 handles everything with no configuration needed.
(function () {
  var h = window.location.hostname;
  var isLocal = h === "localhost" || h === "127.0.0.1" || h === "0.0.0.0" || h === "";
  if (!isLocal) {
    window.FEC_API_BASE = "https://fe-c85291a2a8b144188ee6be1078e79a95.ecs.us-east-1.on.aws";
  }
})();
