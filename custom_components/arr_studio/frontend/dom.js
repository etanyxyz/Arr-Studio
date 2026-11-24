/**
 * Arr Studio frontend - safe DOM builder.
 *
 * All elements are created with document.createElement and text nodes are
 * inserted via textContent/createTextNode; no HTML strings are parsed.
 */

function addChild(node, child) {
  if (typeof child === "string") {
    node.appendChild(document.createTextNode(child));
  } else if (child instanceof Node) {
    node.appendChild(child);
  }
}

export function el(tag, props = {}, ...children) {
  const element = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === null || value === undefined || value === false) {
      continue;
    }
    if (key === "className") {
      element.className = value;
    } else if (key === "style" && typeof value === "object") {
      for (const [styleKey, styleValue] of Object.entries(value)) {
        element.style[styleKey] = styleValue;
      }
    } else if (key === "value" || key === "checked" || key === "hidden") {
      element[key] = value;
    } else if (key.startsWith("on") && typeof value === "function") {
      element.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (key === "dataset") {
      for (const [dsKey, dsValue] of Object.entries(value)) {
        element.dataset[dsKey] = dsValue;
      }
    } else if (key === "aria") {
      for (const [ariaKey, ariaValue] of Object.entries(value)) {
        element.setAttribute("aria-" + ariaKey, ariaValue);
      }
    } else {
      element.setAttribute(key, value === true ? "" : String(value));
    }
  }
  for (const child of children) {
    addChild(element, child);
  }
  return element;
}

export function clear(node) {
  while (node.firstChild) {
    node.removeChild(node.firstChild);
  }
}

export function emptyState(text) {
  return el("div", { className: "empty-state" }, text);
}
