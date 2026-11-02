"use strict";

const MAX_BYTES = 10 * 1024 * 1024;
const SVG = "http://www.w3.org/2000/svg";
const STEP_NAMES = {
  segment_whole: "Segmented the whole image",
  segment_tiled: "Segmented 9 overlapping tiles",
  view_overlay: "Looked at the outlines",
  recheck_cell: "Rechecked one cell",
  compute_cfu: "Computed CFU/mL",
  flag: "Flagged for review",
  finish: "Finished",
  verify: "Verifier",
  fallback: "Fixed counting method",
};
const STATUS_TEXT = {
  verified: "Verified: every number matches a tool output.",
  fallback: "The agent did not finish, so the fixed counting method produced this result.",
};

const $ = (id) => document.getElementById(id);

function show(screen) {
  for (const id of ["upload", "waiting", "result"]) $(id).hidden = id !== screen;
  window.scrollTo(0, 0);
}

function showError(text) {
  $("error").textContent = text;
  $("error").hidden = !text;
  show("upload");
}

function element(tag, text) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  return node;
}

function formatted(value) {
  return Number(value).toLocaleString("en-US");
}

function plainPlate(sample) {
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", `0 0 ${sample.width} ${sample.height}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Colony outlines on a plain plate");
  const plate = document.createElementNS(SVG, "rect");
  plate.setAttribute("width", sample.width);
  plate.setAttribute("height", sample.height);
  plate.setAttribute("fill", "#20302a");
  svg.append(plate);
  for (const [x1, y1, x2, y2] of sample.boxes) {
    const box = document.createElementNS(SVG, "rect");
    box.setAttribute("x", x1);
    box.setAttribute("y", y1);
    box.setAttribute("width", x2 - x1 + 1);
    box.setAttribute("height", y2 - y1 + 1);
    box.setAttribute("fill", "none");
    box.setAttribute("stroke", "#7dff9b");
    box.setAttribute("stroke-width", "2");
    box.setAttribute("vector-effect", "non-scaling-stroke");
    svg.append(box);
  }
  return svg;
}

function renderPicture(data, sampleId) {
  const picture = $("picture");
  picture.replaceChildren();
  const img = element("img");
  img.alt = "The plate with counted colonies outlined";
  if (sampleId) {
    img.onerror = () => {
      picture.replaceChildren(
        plainPlate(data),
        element("p", "This copy has no plate photo, so the outlines are on a plain background."),
      );
      picture.lastChild.className = "muted small";
    };
    img.src = `/samples/${encodeURIComponent(sampleId)}/overlay.jpg`;
  } else {
    img.src = `data:image/jpeg;base64,${data.overlay_jpeg}`;
  }
  picture.append(img);
}

function renderNotes(data) {
  const notes = [];
  if (!data.cfu_basis && data.assumed.includes("dilution")) notes.push("Dilution not given: undiluted assumed.");
  if (!data.cfu_basis && data.assumed.includes("volume_ml")) notes.push("Volume not given: 1 mL assumed.");
  if (data.true_count !== undefined) notes.push(`AGAR label: ${data.true_count} colonies.`);
  if (data.note) notes.push(data.note);
  if (data.credit) notes.push(data.credit + ".");
  $("notes").textContent = notes.join(" ");
}

function renderSteps(steps, sampleId) {
  $("steps").replaceChildren(
    ...steps.map((step) => {
      const item = element("li");
      item.append(element("strong", STEP_NAMES[step.tool] || step.tool));
      const timing = sampleId ? "" : ` (${(step.ms / 1000).toFixed(1)} s, $${step.cost_usd.toFixed(4)})`;
      item.append(element("span", step.summary + timing));
      return item;
    }),
  );
}

function render(data, sampleId) {
  const report = data.report;
  const rejected = report.status === "rejected";
  $("status").textContent = rejected
    ? `Rejected by the verifier: ${report.reason}`
    : STATUS_TEXT[report.status];
  $("status").className = `status ${report.status}`;
  $("count").textContent = rejected ? "None" : formatted(report.colonies);
  $("cfu").textContent = rejected ? "None" : formatted(report.cfu_per_ml);
  $("cfu-label").textContent = data.cfu_basis ? `CFU/mL estimate (${data.cfu_basis})` : "CFU/mL estimate";
  renderPicture(data, sampleId);
  renderNotes(data);
  $("flags").replaceChildren(...data.flags.map((flag) => element("li", flag.text)));
  $("flags-block").hidden = data.flags.length === 0;
  renderSteps(data.steps, sampleId);
  $("cost").textContent = sampleId
    ? "Precomputed: this demo plate made no API calls."
    : `API cost for this plate: $${report.cost_usd.toFixed(4)}`;
  $("error").hidden = true;
  show("result");
}

async function errorText(response) {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // Not JSON: fall through to the plain message.
  }
  return "Something went wrong. Please try again.";
}

async function sendPhoto(file) {
  if (file.size > MAX_BYTES) {
    showError("The photo must be 10 MB or smaller.");
    return;
  }
  const params = new URLSearchParams();
  if ($("dilution").value.trim()) params.set("dilution", $("dilution").value.trim());
  if ($("volume").value.trim()) params.set("volume_ml", $("volume").value.trim());
  show("waiting");
  try {
    const response = await fetch(`/plates?${params}`, {
      method: "POST",
      headers: { "Content-Type": file.type || "application/octet-stream" },
      body: file,
    });
    if (response.ok) render(await response.json(), null);
    else showError(await errorText(response));
  } catch {
    showError("Could not reach the server. Check the connection and try again.");
  }
}

async function openSample(id) {
  try {
    const response = await fetch(`/samples/${encodeURIComponent(id)}`);
    if (response.ok) render(await response.json(), id);
    else showError(await errorText(response));
  } catch {
    showError("Could not reach the server. Check the connection and try again.");
  }
}

async function loadSamples() {
  try {
    const response = await fetch("/samples");
    const samples = response.ok ? await response.json() : [];
    $("sample-buttons").replaceChildren(
      ...samples.map((sample) => {
        const button = element("button", sample.label);
        button.type = "button";
        button.className = "button secondary";
        button.addEventListener("click", () => openSample(sample.id));
        return button;
      }),
    );
    $("samples").hidden = samples.length === 0;
  } catch {
    $("samples").hidden = true;
  }
}

for (const id of ["camera", "gallery"]) {
  $(id).addEventListener("change", (event) => {
    const file = event.target.files[0];
    event.target.value = "";
    if (file) sendPhoto(file);
  });
}
$("again").addEventListener("click", () => show("upload"));
loadSamples();
