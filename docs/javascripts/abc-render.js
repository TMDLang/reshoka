(function () {
  function sanitizeAbc(abcText) {
    // In the ABC specification, a blank line terminates a tune.
    // Remove internal blank lines within a single X:1 tune so abcjs parses the body after K:.
    return abcText
      .split(/\r?\n/)
      .filter(function (line) {
        return line.trim().length > 0;
      })
      .join("\n");
  }

  function renderAllAbcBlocks(root) {
    if (typeof ABCJS === "undefined") {
      return;
    }
    var scope = root || document;
    var codeNodes = scope.querySelectorAll(
      ".language-abc code, div.highlight-abc code, code.language-abc, pre.abc > code"
    );

    codeNodes.forEach(function (codeEl) {
      var wrapper =
        codeEl.closest(".language-abc, .highlight-abc, pre.abc") ||
        codeEl.parentElement;
      if (!wrapper || wrapper.dataset.abcRendered === "true") {
        return;
      }
      var rawAbc = (codeEl.textContent || "").trim();
      var abcText = sanitizeAbc(rawAbc);
      if (!abcText) {
        return;
      }

      wrapper.dataset.abcRendered = "true";

      var scoreContainer = document.createElement("div");
      scoreContainer.className = "abc-score-container";
      wrapper.parentNode.insertBefore(scoreContainer, wrapper);

      ABCJS.renderAbc(scoreContainer, abcText, {
        responsive: "resize",
        add_classes: true,
        paddingtop: 15,
        paddingbottom: 15,
        paddingright: 15,
        paddingleft: 15,
      });
    });
  }

  if (typeof document$ !== "undefined" && document$.subscribe) {
    document$.subscribe(function (body) {
      renderAllAbcBlocks(body);
    });
  } else {
    document.addEventListener("DOMContentLoaded", function () {
      renderAllAbcBlocks(document);
    });
  }
})();
