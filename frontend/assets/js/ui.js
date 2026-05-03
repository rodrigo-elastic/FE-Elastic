/*
  filename: ui.js
  description: DOM helpers, toast notifications, simple builders.
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/
function setText(id, text) {
  const elNode = document.getElementById(id);
  if (elNode) elNode.textContent = text;
}

function el(tag, attrs, children) {
  const node = document.createElement(tag);
  if (attrs) {
    Object.entries(attrs).forEach(([k, v]) => {
      if (v == null || v === false) return;
      if (k === "class") node.className = v;
      else if (k === "html") node.innerHTML = v;
      else if (k === "text") node.textContent = v;
      else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
      else if (v === true) node.setAttribute(k, "");
      else node.setAttribute(k, v);
    });
  }
  const list = Array.isArray(children) ? children : children == null ? [] : [children];
  list.forEach((c) => {
    if (c == null) return;
    node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  });
  return node;
}

function clear(node) {
  while (node && node.firstChild) node.removeChild(node.firstChild);
}

function toast(message, kind) {
  const host = document.getElementById("toast-host") || document.body;
  const node = el("div", { class: "toast" + (kind ? " " + kind : "") }, message);
  host.appendChild(node);
  setTimeout(() => node.remove(), 3500);
}

function fmtDate(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString();
  } catch (e) {
    return iso;
  }
}

function setBusy(button, busy, idleLabel) {
  if (!button) return;
  button.disabled = !!busy;
  button.textContent = busy ? "Working..." : idleLabel;
}
