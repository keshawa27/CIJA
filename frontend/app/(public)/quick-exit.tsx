"use client";

// Leaves immediately for a neutral site. `replace` keeps this page out of the
// back-button history, so pressing Back does not return here.
export default function QuickExit() {
  return (
    <button
      type="button"
      onClick={() => window.location.replace("https://www.bom.gov.au/")}
      className="fixed right-4 bottom-4 z-50 cursor-pointer rounded-md bg-red-700 px-4 py-3 text-sm font-bold text-white shadow-lg hover:bg-red-800"
    >
      Quick exit ✕
    </button>
  );
}
