import "./print-artifact.css";

/**
 * Print one rendered artifact without allowing hidden application layout to create
 * blank pages or other printable artifacts to leak into the same print job.
 *
 * The source node is cloned into a temporary top-level print portal. The live UI
 * stays untouched and the portal is removed as soon as the browser print dialog
 * returns.
 */
export function printArtifact(selector: string): boolean {
  const source = window.document.querySelector<HTMLElement>(selector);
  if (!source) return false;

  const portal = window.document.createElement("div");
  portal.className = "tpp-print-portal";
  portal.setAttribute("aria-hidden", "true");
  portal.appendChild(source.cloneNode(true));

  window.document.body.appendChild(portal);
  window.document.body.classList.add("tpp-printing-artifact");
  try {
    window.print();
  } finally {
    window.document.body.classList.remove("tpp-printing-artifact");
    portal.remove();
  }
  return true;
}
