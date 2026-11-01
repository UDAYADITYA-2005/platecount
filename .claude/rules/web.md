---
paths:
  - "web/**"
  - "src/platecount/api/**/*.py"
---

# Web and API rules

- Plain HTML, CSS and JavaScript in `web/`; no build step, no framework.
- Must work at 360 px width. Primary button at least 48 px tall.
- Use `<input type="file" accept="image/*" capture="environment">` for the camera.
- Show the agent's steps as they happen (or right after), not only the final number.
- Wording: "colony count" and "CFU/mL estimate". Never "safe", "contaminated", "diagnosis" or health claims.
- The API key stays on the server. Rate limit: 10 plates per visitor per hour. Max upload 10 MB.
- Visitor photos: process in memory or a temp folder, delete within 24 hours, never log them.
- Show one line under the upload button: "Your photo is sent to Meta's API to count colonies and is deleted within 24 hours."
