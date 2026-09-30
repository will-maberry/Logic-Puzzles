// Display shared solved-board animation inside board frame
function celebrateBoard(frame) {
  // Remove existing celebration if there is one
  frame.querySelector(".board-celebration")?.remove();

  const layer = document.createElement("div");
  layer.className = "board-celebration";
  layer.setAttribute("aria-hidden", "true");

  const badge = document.createElement("span");
  badge.className = "board-win-badge";
  badge.textContent = "SOLVED";

  layer.appendChild(badge);

  // OS/browser reduced motion check
    // Solved badge appears but no confetti
  if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    const colors = ["#7f9fbd", "#c77d6b", "#83a47d", "#d29b5b", "#9b84ae"];

    // Generate confetti around center of board
    for (let index = 0; index < 24; index++) {
      const piece = document.createElement("span");
      piece.className = "board-confetti";
      piece.style.setProperty("--x", `${18 + Math.random() * 64}%`);
      piece.style.setProperty("--y", `${22 + Math.random() * 46}%`);
      piece.style.setProperty("--dx", `${(Math.random() - 0.5) * 220}px`);
      piece.style.setProperty("--dy", `${-65 - Math.random() * 130}px`);
      piece.style.setProperty("--turn", `${(Math.random() - 0.5) * 540}deg`);
      piece.style.setProperty("--delay", `${Math.random() * 160}ms`);
      piece.style.backgroundColor = colors[index % colors.length];

      layer.appendChild(piece);
    }
  }

  frame.appendChild(layer);

  // Remove DOM elements after animation
  window.setTimeout(() => layer.remove(), 1900);
}