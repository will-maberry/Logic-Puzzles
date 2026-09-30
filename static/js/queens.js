/*
Queens Game Front-End
*/

// configuration and game state
const queensApi = "/api/queens";
const queensSaveKey = "queenGameSave";

// Saved game lifetime
const saveLifetimeMs = 30 * 60 * 1000;

// Region colors for game (must equal maximum n)
const queenPalette = ["#7f9fbd", "#c77d6b", "#83a47d", "#9b84ae", "#d29b5b", "#d4c76d", "#a87e69", "#c68fa5", "#939ba3", "#72a69e"];

// Game difficulty = board size = number queens
const queenPresets = {easy: [4, 5, 6], medium: [7, 8], hard: [9, 10]};


let queensLevel = "easy";
let queenPuzzle = null;
let queens = [];
let notes = [];
let queensFinished = false;

// Increment when asynchronous game stat changes
let queensVersion = 0;

// Track right-button drag
let queenMarkDrag = null;

/*
Board Interaction
*/

// Draw or erase X note while right-button clicked
function paintQueenMark(row, col) {
  if (!queenMarkDrag || !queenPuzzle || queensFinished ||
      row < 0 || col < 0 || row >= queenPuzzle.size || col >= queenPuzzle.size) return;

  const key = `${row},${col}`;
  if (queenMarkDrag.visited.has(key)) return;

  queenMarkDrag.visited.add(key);

  // Notes can't go on square where queen currently is
  if (queens[row][col]) return;

  notes[row][col] = queenMarkDrag.value;
  drawQueens();
}

// Place or remove queen in cell
function placeQueen(row, col) {
  const region = queenPuzzle.regions[row][col];
  const wasOccupied = queens[row][col] === 1;

  for (let boardRow = 0; boardRow < queenPuzzle.size; boardRow++) {
    for (let boardCol = 0; boardCol < queenPuzzle.size; boardCol++) {
      if (queenPuzzle.regions[boardRow][boardCol] === region) {
        queens[boardRow][boardCol] = 0;
      }
    }
  }

  // Clicking occupied cell removes queen and vice-versa
  if (!wasOccupied) {
    queens[row][col] = 1;
    notes[row][col] = 0;
  }

  checkQueens();
}

// Remove multiple queens in same region
function normalizeQueensByRegion() {
  const occupiedRegions = new Set();

  for (let row = 0; row < queenPuzzle.size; row++) {
    for (let col = 0; col < queenPuzzle.size; col++) {
      if (!queens[row][col]) continue;

      const region = queenPuzzle.regions[row][col];

      if (occupiedRegions.has(region)) queens[row][col] = 0;

      else occupiedRegions.add(region);
    }
  }
}

/*
Status and API
*/

// Display game-status message below board
function queensStatus(message) {
  document.getElementById("status").textContent = message;
}

// Send JSON to queens API endpoint and return decoded response
  // HTTP errors converted into errors carrying response status to display to player
async function queensPost(path, payload) {
  const response = await fetch(`${queensApi}${path}`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
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
function queensApiError(error, action) {
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

// Render current game board as SVG
  // Region IDs determine cell colors
  // Quenns and X notes added as SVG images
  // Conflicts returned by API are highlighted
function drawQueens(conflicts = []) {
  const board = document.getElementById("board");
  board.replaceChildren();

  if (!queenPuzzle) return;

  const size = queenPuzzle.size;
  const side = 800 / size;

  const conflictCells = new Set(
    conflicts.map(([row, col]) => `${row},${col}`)
  );

  const svg = "http://www.w3.org/2000/svg";

  for (let row = 0; row < size; row++) {
    for (let col = 0; col < size; col++) {
      const cell = document.createElementNS(svg, "rect");

      cell.setAttribute("x", col * side);
      cell.setAttribute("y", row * side);
      cell.setAttribute("width", side);
      cell.setAttribute("height", side);

      cell.setAttribute(
        "fill",
        conflictCells.has(`${row},${col}`)
          ? "lightcoral"
          : queenPalette[
              queenPuzzle.regions[row][col] %
              queenPalette.length
            ]
      );

      cell.setAttribute("stroke", "black");
      cell.setAttribute("role", "button");

      // Coordinates are stored on each SVG cell for pointer handler to recover board position
      cell.dataset.row = String(row);
      cell.dataset.col = String(col);

      cell.setAttribute(
        "aria-label",
        `Row ${row + 1}, column ${col + 1}`
      );

      cell.addEventListener("click", () => {
        if (queensFinished) return;
        placeQueen(row, col);
      });

      board.appendChild(cell);

      // Render queen or X note over underlying region cell
      if (queens[row][col] || notes[row][col]) {
        const mark = document.createElementNS(svg, "image");

        const iconSize = side * (queens[row][col] ? 0.58 : 0.38);

        mark.setAttribute("x", col * side + (side - iconSize) / 2);
        mark.setAttribute("y", row * side + (side - iconSize) / 2);

        mark.setAttribute("width", iconSize);
        mark.setAttribute("height", iconSize);

        mark.setAttribute(
          "href",
          queens[row][col]
            ? "/static/icons/chess-queen.svg"
            : "/static/icons/xmark.svg"
        );

        board.appendChild(mark);
      }
    }
  }
}

/*
Puzzle Generation and Difficulty
*/

// Request to initialize a new puzzle for selected difficulty
  // Board size chosen from difficulty preset before server generation
async function newQueens(discardSave = false) {
  const sizes = queenPresets[queensLevel];

  const size = sizes[Math.floor(Math.random() * sizes.length)];

  const version = ++queensVersion;

  queensStatus("Generating puzzle...");

  try {
    const result = await queensPost(
      "/generate",
      {size}
    );

    // Ignore response if anotehr state-changing action occurred
    if (version !== queensVersion) return;

    let saveClearFailed = false;

    // Starting a new puzzle deletes local save
    if (discardSave) {
      try { localStorage.removeItem(queensSaveKey); }
      catch (_) { saveClearFailed = true; }
    }

    queenPuzzle = result;
    queensFinished = false;

    queens = Array.from(
      {length: size},
      () => Array(size).fill(0)
    );

    notes = Array.from(
      {length: size},
      () => Array(size).fill(0)
    );

    document.getElementById(
      "puzzleMeta"
    ).textContent = `${size}x${size} BOARD`;

    drawQueens();

    queensStatus(
      saveClearFailed
        ? "New puzzle loaded, but browser storage could not be cleared."
        : "Place one queen in each region."
    );

  } catch (error) {
    if (version === queensVersion) {
      queensStatus(
        queensApiError(error, "generate a puzzle")
      );
    }
  }
}

// Change difficulty and generate puzzle from that preset
function selectQueensDifficulty(level) {
  if (!Object.hasOwn(queenPresets, level)) return;

  queensLevel = level;
  syncQueensDifficulty();
  newQueens(true);
}

// Synchronize difficulty-button with selected difficulty
function syncQueensDifficulty() {
  document.querySelectorAll(".difficulty-options [data-level]").forEach(button => {
    button.setAttribute("aria-pressed", String(button.dataset.level === queensLevel));
  });
}

/*
Board Checking and Solution Display
*/

// Submit current board to API for conflict and win checks
async function checkQueens() {
  if (!queenPuzzle) return;

  const version = ++queensVersion;

  // Clear previously displayed conflicts while new state checked
  drawQueens();
  queensStatus("Checking...");

  try {
    const result = await queensPost("/check", {
      size: queenPuzzle.size, board: queens, regions: queenPuzzle.regions
    });

    // Newer board action makes response obsolete
    if (version !== queensVersion) return;

    // Selebate only transition into solved state
    if (result.win && !queensFinished) {
      celebrateBoard(
        document.querySelector(".board-frame")
      );
    }

    queensFinished = result.win;

    drawQueens(result.conflicts);

    queensStatus(
      result.win
        ? "Solved!"
        : result.conflicts.length
          ? "Queen conflicts detected."
          : "Keep going."
    );
  } catch (error) {
    if (version === queensVersion) {
      queensStatus(
        queensApiError(error, "check this move")
      );
    }
  }
}

// Replace current board with solution returned at generation
function revealQueens() {
  if (!queenPuzzle) return;

  if (!Array.isArray(queenPuzzle.solution)) {
    queensStatus("The solution is unavailable for this saved puzzle.");

    return;
  }

  // Invalidate pending checks
  queensVersion += 1;

  queens = Array.from({length: queenPuzzle.size}, () => Array(queenPuzzle.size).fill(0));

  // Solutions store queen column for each row
  queenPuzzle.solution.forEach((col, row) => { queens[row][col] = 1; });

  queensFinished = true;

  drawQueens();
  queensStatus("Solution revealed.");
}


/*
Local Save Storage
*/

// Save current puzzle and state to player's localStorage in browser
function saveQueens() {
  if (!queenPuzzle) {
    queensStatus("Load a puzzle before saving.");
    return;
  }

  const saved = {
    timestamp: Date.now(), puzzle: queenPuzzle, board: queens,
    notes, finished: queensFinished, level: queensLevel
  };

  try {
    localStorage.setItem(queensSaveKey, JSON.stringify(saved));
    queensStatus("Game saved in this browser for 30 minutes.");
  } catch (_) {
    queensStatus("Browser storage is unavailable.");
  }
}

// Check if stored matrix has expected dimensions and values
function queensMatrixValid(matrix, size, maxValue) {
  return (
    Array.isArray(matrix) &&
    matrix.length === size &&
    matrix.every(row =>
      Array.isArray(row) &&
      row.length === size &&
      row.every(value =>
        Number.isInteger(value) &&
        value >= 0 &&
        value <= maxValue
      )
    )
  );
}

// Validate complete structure of browser save
function validQueensSave(saved) {
  if (!saved || typeof saved !== "object") return false;

  const puzzle = saved.puzzle || saved;
  const size = puzzle.size;

  if (!Number.isInteger(size) || size < 4 || size > 10) return false;

  if (!queensMatrixValid(puzzle.regions, size, size - 1) ||
      !queensMatrixValid(saved.board, size, 1) ||
      !queensMatrixValid(saved.notes, size, 1)) return false;
  
  const regions = new Set(puzzle.regions.flat());

  if (regions.size !== size) return false;

  // Older or altered saves may not have a solution
  if (puzzle.solution !== undefined && puzzle.solution !== null &&
      (!Array.isArray(puzzle.solution) || puzzle.solution.length !== size ||
       !puzzle.solution.every(col => Number.isInteger(col) && col >= 0 && col < size))) return false;
  
  // Reject future timestamps and saves older than lifetime
  return Number.isFinite(saved.timestamp) && saved.timestamp <= Date.now() &&
    Date.now() - saved.timestamp <= saveLifetimeMs;
}

/*
Restore valid and unexpired save from browser
*/
function loadQueens() {
  let saved;

  try {
    const raw = localStorage.getItem(queensSaveKey);
    if (!raw) {
      queensStatus("No saved game found.");
      return;
    }

    // Refuse loading large saved values before parsing them
    if (raw.length > 50000) throw new Error("Saved game is too large");
    saved = JSON.parse(raw);
  } catch (_) {
    queensStatus("Saved game could not be read.");
    return;
  }

  // Expired saves should be removed rather than living in browser storage
  if (saved && Number.isFinite(saved.timestamp) && Date.now() - saved.timestamp > saveLifetimeMs) {
    try { localStorage.removeItem(queensSaveKey); } catch (_) {}
    queensStatus("Saved game expired.");
    return;
  }

  if (!validQueensSave(saved)) {
    queensStatus("Saved game is invalid or has expired.");
    return;
  }

  const puzzle = saved.puzzle || saved;

  // Invalidate any pending API response before restoring data
  queensVersion += 1;

  queenPuzzle = {size: puzzle.size, regions: puzzle.regions, solution: puzzle.solution || null};
  
  queens = saved.board;
  notes = saved.notes;

  normalizeQueensByRegion();

  queensFinished = Boolean(saved.finished);

  queensLevel = typeof saved.level === "string" && Object.hasOwn(queenPresets, saved.level)
    ? saved.level : "easy";
  
  syncQueensDifficulty();

  document.getElementById("puzzleMeta").textContent = `${puzzle.size}×${puzzle.size} BOARD`;
  drawQueens();

  queensStatus("Saved game loaded. Checking with the API...");

  // Revalidate restored board with server
  checkQueens();
}

/*
Page Initialization and Event Handlers
*/

document.addEventListener("DOMContentLoaded", () => {
  const board = document.getElementById("board");

  // Board uses right mouse button for X notes so suppress normal right click inside game board
  board.addEventListener("contextmenu", event => event.preventDefault());

  // Begin painting or erasing X notes when right-clicking board cell
  board.addEventListener("pointerdown", event => {
    if (event.button !== 2 || !queenPuzzle || queensFinished) return;
    const cell = event.target.closest("rect[data-row][data-col]");
    if (!cell) return;
    event.preventDefault();
    const row = Number(cell.dataset.row), col = Number(cell.dataset.col);

    // Initial cell determines if paint or erase activated
    queenMarkDrag = {value: notes[row][col] ? 0 : 1, visited: new Set()};

    paintQueenMark(row, col);
  });

  // Continue note painting as pointer moves across board cells
  document.addEventListener("pointermove", event => {
    if (!queenMarkDrag) return;

    // Cancel drag if right mouse button no longer held
    if (!(event.buttons & 2)) { queenMarkDrag = null; return; }

    const cell = document.elementFromPoint(event.clientX, event.clientY)?.closest("rect[data-row][data-col]");
    if (cell && board.contains(cell)) paintQueenMark(Number(cell.dataset.row), Number(cell.dataset.col));
  });

  // Ensure drag state can't remain active after interaction ends
  document.addEventListener("pointerup", () => { queenMarkDrag = null; });


  window.addEventListener("blur", () => { queenMarkDrag = null; });

  // Puzzle controls
  document.getElementById("newPuzzle").addEventListener("click", () => newQueens(true));
  document.getElementById("saveGame").addEventListener("click", saveQueens);
  document.getElementById("loadGame").addEventListener("click", loadQueens);

  // Difficulty controls
  document.querySelectorAll(".difficulty-options [data-level]").forEach(button => {
    button.addEventListener("click", () => selectQueensDifficulty(button.dataset.level));
  });
  document.getElementById("revealSolution").addEventListener("click", revealQueens);

  // Help modal
  const modal = document.getElementById("helpModal");
  document.getElementById("helpButton").addEventListener("click", () => { modal.style.display = "block"; });
  document.getElementById("closeHelp").addEventListener("click", () => { modal.style.display = "none"; });
  
  // Clicking background closes modal
  modal.addEventListener("click", event => { if (event.target === modal) modal.style.display = "none"; });
  
  // Escape key also closes modal
  document.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      modal.style.display = "none";
    }
  });

  // Begin with newly generated puzzle
  newQueens();
});