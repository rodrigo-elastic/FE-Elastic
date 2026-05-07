// FE Copilot - backend URL configuration
// This file is loaded before all other scripts on every page.
//
// LOCAL DEV: leave window.FEC_API_BASE undefined (or comment it out).
//   The app uses relative /api/v1 paths → FastAPI on localhost:8123.
//
// GITHUB PAGES → AWS: set the value below to your ECS/App Runner URL.
//   Update this line and push; GitHub Actions redeploys automatically.
//
window.FEC_API_BASE = "https://fe-c85291a2a8b144188ee6be1078e79a95.ecs.us-east-1.on.aws";
