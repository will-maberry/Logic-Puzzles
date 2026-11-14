/* 
Luminosa Game Front-End
*/

// Configuration and game state
const luminosaApi = "/api/luminosa";
const luminosaSaveKey = "luminosaGameSave";

// Saved game lifetime
const luminosaSaveLifetimeMs = 30 * 60 * 1000;

// Board sizes for different difficulties
const luminosaPresets = {easy: [5, 6], medium: [7, 8], hard: [9, 10]};

let luminosaLevel = "easy";
let luminosaPuzzle = null;
let luminosaBoard = [];
let luminosaNotes = [];
let luminosaFinished = false;

// Increment when asynchronous game stat changes
let luminosaVersion = 0;

// Track right-button drag
let lightMarkDrag = null;

/*
Status and API
*/


// Display game-status message below board
function luminosaStatus(message) {
  document.getElementById("status").textContent = message;
}

// Send JSON to luminosa API endpoint and return decoded response
  // HTTP errors converted into errors carrying response status to display to player
async function luminosaPost(path, payload) {
  const response = await fetch(`${luminosaApi}${path}`, {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    const error = new Error("API request failed");
    error.status = response.status;
    throw error;
  }
  return response.json();
}

// Convert API failure into player-facing status message
// Convert API failure into player-facing status message
function luminosaApiError(error, action) {
  if (error?.status === 429) {
    return "Too many requests. Try again in a minute.";
  }

  if (error?.status === 404 || error?.status === 405) {
    return "Puzzle API route unavailable. Run the current FastAPI app.";
  }

  return `The API could not ${action}. Try again.`;
}

/*
Board Rendering
*/

function wallKeys() {
  const walls = new Set();
  luminosaPuzzle.cells.forEach((row, r) => row.forEach((value, c) => {
    if (value !== -2) walls.add(`${r},${c}`);
  }));
  return walls;
}

function svgNode(tag, attributes) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
  return node;
}

// Render curernt game board as SVG
function drawLuminosa(conflicts = []) {
  const board = document.getElementById("board");
  board.replaceChildren();
  if (!luminosaPuzzle) return;
  const {size, cells} = luminosaPuzzle;
  const side = 800 / size;
  const lit = new Set();
  const conflictCells = new Set(conflicts.map(cell => cell.join(",")));
  for (let r = 0; r < size; r++) for (let c = 0; c < size; c++) {
    if (!luminosaBoard[r][c] || cells[r][c] !== -2) continue;
    lit.add(`${r},${c}`);
    for (const [dr, dc] of [[-1, 0], [1, 0], [0, -1], [0, 1]]) {
      let row = r + dr, col = c + dc;
      while (row >= 0 && row < size && col >= 0 && col < size && cells[row][col] === -2) {
        lit.add(`${row},${col}`);
        row += dr; col += dc;
      }
    }
  }
  for (let row = 0; row < size; row++) for (let col = 0; col < size; col++) {
    const key = `${row},${col}`;
    const wall = cells[row][col] !== -2;
    const cell = svgNode("rect", {
      x: col * side, y: row * side, width: side, height: side,
      class: "light-cell", "stroke-width": 1, stroke: "#887c56",
      fill: conflictCells.has(key) ? "lightcoral" : wall ? "#303331" : lit.has(key) ? "#f5de8e" : "#eee9d9",
      role: wall ? "img" : "button", tabindex: wall ? -1 : 0,
      "aria-label": `Row ${row + 1}, column ${col + 1}, ${wall ? cells[row][col] >= 0 ? `wall clue ${cells[row][col]}` : "wall" : luminosaBoard[row][col] ? "light" : luminosaNotes[row][col] ? "X mark" : lit.has(key) ? "lit" : "unlit"}`
    });
    cell.dataset.row = row; cell.dataset.col = col;
    const toggle = () => {
      if (luminosaFinished || wall) return;
      luminosaBoard[row][col] = luminosaBoard[row][col] ? 0 : 1;
      luminosaNotes[row][col] = 0;
      checkLuminosa();
    };
    cell.addEventListener("click", toggle);
    cell.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); toggle(); }
    });
    board.appendChild(cell);
    if (wall && cells[row][col] >= 0) {
      const label = svgNode("text", {x: (col + .5) * side, y: (row + .5) * side,
        "text-anchor": "middle", "dominant-baseline": "central", fill: "#fff",
        "font-size": side * .42, "font-family": "monospace", "pointer-events": "none"});
      label.textContent = cells[row][col];
      board.appendChild(label);
    }
    const icon = wall ? null : luminosaBoard[row][col] ? "lightbulb.svg" : luminosaNotes[row][col] ? "xmark.svg" : null;
    if (icon) {
      const width = side * (icon === "xmark.svg" ? .32 : .55);
      const mark = svgNode("image", {x: col * side + (side - width) / 2,
        y: row * side + (side - width) / 2, width, height: width, href: `/static/icons/${icon}`});
      mark.style.filter = "none";
      board.appendChild(mark);
    }
  }
}

// Paint X marks
function paintLightMark(row, col) {
  if (!lightMarkDrag || !luminosaPuzzle || luminosaFinished ||
      row < 0 || col < 0 || row >= luminosaPuzzle.size || col >= luminosaPuzzle.size) return;
  
  const key = `${row},${col}`;

  // Each cell changed at most once per drag
    // cells with walls and lights can't receive X
  if (lightMarkDrag.visited.has(key) || wallKeys().has(key) || luminosaBoard[row][col]) return;

  lightMarkDrag.visited.add(key);
  luminosaNotes[row][col] = lightMarkDrag.value;

  drawLuminosa();
}

// New puzzle function
async function newLuminosa(discardSave = false) {
  const sizes = luminosaPresets[luminosaLevel];
  const size = sizes[Math.floor(Math.random() * sizes.length)];

  // Capture request version so it's response can be ignored if palyer starts another puzzle before generation complete
  const version = ++luminosaVersion;

  luminosaFinished = true;
  luminosaStatus("Generating puzzle...");

  try {
    const puzzle = await luminosaPost("/generate", {size});
    if (version !== luminosaVersion) return;
    let clearFailed = false;
    if (discardSave) {
      try { localStorage.removeItem(luminosaSaveKey); }
      catch (_) { clearFailed = true; }
    }

    luminosaPuzzle = puzzle;
    luminosaBoard = Array.from({length: size}, () => Array(size).fill(0));
    luminosaNotes = Array.from({length: size}, () => Array(size).fill(0));

    luminosaFinished = false;

    document.getElementById("puzzleMeta").textContent = `${size}×${size} BOARD`;
    
    drawLuminosa();

    luminosaStatus(clearFailed ? "New puzzle loaded, but browser storage could not be cleared." : "Light every open cell.");
  } catch (error) {
    if (version === luminosaVersion) { luminosaFinished = false; luminosaStatus(luminosaApiError(error, "generate a puzzle")); }
  }
}

// Set luminosa game difficulty
function syncLuminosaDifficulty() {
  document.querySelectorAll(".difficulty-options [data-level]").forEach(button => {
    button.setAttribute("aria-pressed", String(button.dataset.level === luminosaLevel));
  });
}

// Game board validation
async function checkLuminosa() {
  if (!luminosaPuzzle) return;

  // Each move invalidates and check mid-computation
  const version = ++luminosaVersion;

  drawLuminosa();
  luminosaStatus("Checking...");

  try {
    const {size, cells} = luminosaPuzzle;
    const result = await luminosaPost("/check", {size, cells, board: luminosaBoard});

    // Ignore checks from old state
    if (version !== luminosaVersion) return;

    if (result.win && !luminosaFinished) celebrateBoard(document.querySelector(".board-frame"));

    luminosaFinished = result.win;

    drawLuminosa(result.conflicts);

    luminosaStatus(result.win ? "Solved!" : result.conflicts.length ? "Light or wall clue conflicts detected." : "Keep going.");
  } catch (error) {
    if (version === luminosaVersion) luminosaStatus(luminosaApiError(error, "check this move"));
  }
}

// Reveal puzzle solution
function revealLuminosa() {
  if (!luminosaPuzzle) return;

  if (!Array.isArray(luminosaPuzzle.solution)) {
    luminosaStatus("The solution is unavailable for this saved puzzle.");
    return;
  }

  // Invalidate API responses before replacing board
  ++luminosaVersion;

  const size = luminosaPuzzle.size;

  luminosaBoard = Array.from({length: size}, () => Array(size).fill(0));

  for (const [row, col] of luminosaPuzzle.solution) luminosaBoard[row][col] = 1;
  luminosaNotes = Array.from({length: size}, () => Array(size).fill(0));

  luminosaFinished = true;

  drawLuminosa();
  luminosaStatus("Solution revealed.");
}

// Local save and load
function saveLuminosa() {
  if (!luminosaPuzzle) { luminosaStatus("Load a puzzle before saving."); return; }

  try {
    localStorage.setItem(luminosaSaveKey, JSON.stringify({
      timestamp: Date.now(), puzzle: luminosaPuzzle, board: luminosaBoard,
      notes: luminosaNotes, finished: luminosaFinished, level: luminosaLevel
    }));

    luminosaStatus("Game saved in this browser for 30 minutes.");

  } catch (_) { luminosaStatus("Browser storage is unavailable."); }
}

// See if matrix is valid dimensions and correctly formatted
function matrixValid(matrix, size) {
  return Array.isArray(matrix) && matrix.length === size && matrix.every(row =>
    Array.isArray(row) && row.length === size && row.every(value => value === 0 || value === 1));
}

function validLuminosaSave(saved) {
  if (!saved || typeof saved !== "object" || !saved.puzzle) return false;
  const {size, cells, solution} = saved.puzzle;
  if (!Number.isInteger(size) || size < 4 || size > 10 ||
      !matrixValid(saved.board, size) || !matrixValid(saved.notes, size)) return false;
  if (!Array.isArray(cells) || cells.length !== size || !cells.every(row =>
      Array.isArray(row) && row.length === size && row.every(v => Number.isInteger(v) && v >= -2 && v <= 4)) ||
      !cells.some(row => row.includes(-2))) return false;
  if (!Array.isArray(solution) || !solution.length || !solution.every(pair =>
      Array.isArray(pair) && pair.length === 2 && pair.every(v => Number.isInteger(v) && v >= 0 && v < size) &&
      cells[pair[0]][pair[1]] === -2) || new Set(solution.map(pair => pair.join(","))).size !== solution.length) return false;
  for (let r = 0; r < size; r++) for (let c = 0; c < size; c++) {
    if (cells[r][c] !== -2 && (saved.board[r][c] || saved.notes[r][c])) return false;
  }
  return typeof saved.finished === "boolean" && Object.hasOwn(luminosaPresets, saved.level) &&
    Number.isFinite(saved.timestamp) && saved.timestamp <= Date.now() &&
    Date.now() - saved.timestamp <= luminosaSaveLifetimeMs;
}

// Load luminosa
function loadLuminosa() {
  let saved;

  try {
    const raw = localStorage.getItem(luminosaSaveKey);

    if (!raw) { luminosaStatus("No saved game found."); return; }

    // Don't load arbitrarily large saves
    if (raw.length > 50000) throw new Error("Saved game is too large");

    saved = JSON.parse(raw);

  } catch (_) { luminosaStatus("Saved game could not be read."); return; }

  // Expired saves removed
  if (saved && Number.isFinite(saved.timestamp) && Date.now() - saved.timestamp > luminosaSaveLifetimeMs) {
    try { localStorage.removeItem(luminosaSaveKey); } catch (_) {}
    luminosaStatus("Saved game expired.");
    return;
  }

  if (!validLuminosaSave(saved)) { luminosaStatus("Saved game is invalid or has expired."); return; }

  // Loading replaces active game, so invalidate pending API requests
  ++luminosaVersion;

  luminosaPuzzle = saved.puzzle;
  luminosaBoard = saved.board;
  luminosaNotes = saved.notes;
  luminosaFinished = Boolean(saved.finished);

  luminosaLevel = Object.hasOwn(luminosaPresets, saved.level) ? saved.level : "easy";

  syncLuminosaDifficulty();

  document.getElementById("puzzleMeta").textContent = `${luminosaPuzzle.size}×${luminosaPuzzle.size} BOARD · LIGHT EVERY CELL`;

  drawLuminosa();

  // Check restored state with server instead of trusting localStorage
  luminosaStatus("Saved game loaded. Checking with the API...");
  checkLuminosa();
}

/*
Event Handlers
*/

document.addEventListener("DOMContentLoaded", () => {
  const board = document.getElementById("board");

  // Right-click for X marks and stop default action
  board.addEventListener("contextmenu", event => event.preventDefault());

  // Start painting or removing X marks
  board.addEventListener("pointerdown", event => {
    if (event.button !== 2 || !luminosaPuzzle || luminosaFinished) return;

    const cell = event.target.closest("rect[data-row][data-col]");

    if (!cell) return;

    event.preventDefault();

    const row = Number(cell.dataset.row), col = Number(cell.dataset.col);

    lightMarkDrag = {value: luminosaNotes[row][col] ? 0 : 1, visited: new Set()};
    paintLightMark(row, col);
  });

  // Continue painting as long as right-click pressed
  document.addEventListener("pointermove", event => {
    if (!lightMarkDrag) return;

    if (!(event.buttons & 2)) { lightMarkDrag = null; return; }

    const cell = document.elementFromPoint(event.clientX, event.clientY)?.closest("rect[data-row][data-col]");
    
    if (cell && board.contains(cell)) paintLightMark(Number(cell.dataset.row), Number(cell.dataset.col));
  });

  // Terminate drag when pointer released
  document.addEventListener("pointerup", () => { lightMarkDrag = null; });
  window.addEventListener("blur", () => { lightMarkDrag = null; });

  // Game controls
  document.getElementById("newPuzzle").addEventListener("click", () => newLuminosa(true));
  document.getElementById("saveGame").addEventListener("click", saveLuminosa);
  document.getElementById("loadGame").addEventListener("click", loadLuminosa);
  document.getElementById("revealSolution").addEventListener("click", revealLuminosa);

  // Changing difficulty causes new puzzle to be generated
  document.querySelectorAll(".difficulty-options [data-level]").forEach(button => {
    button.addEventListener("click", () => {
      if (!Object.hasOwn(luminosaPresets, button.dataset.level)) return;

      luminosaLevel = button.dataset.level;

      syncLuminosaDifficulty();
      newLuminosa(true);
    });
  });

  // Help modal
  const modal = document.getElementById("helpModal");

  document.getElementById("helpButton").addEventListener("click", () => { modal.style.display = "block"; });

  document.getElementById("closeHelp").addEventListener("click", () => { modal.style.display = "none"; });

  modal.addEventListener("click", event => { if (event.target === modal) modal.style.display = "none"; });

  document.addEventListener("keydown", event => { if (event.key === "Escape") modal.style.display = "none"; });

  // Always generate new puzzle on page load
  newLuminosa();
});