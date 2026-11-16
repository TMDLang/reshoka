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

  function renderAbc(scoreContainer, abcText) {
    var normalized = sanitizeAbc(abcText);
    if (!normalized) {
      return;
    }

    scoreContainer.dataset.abcRendered = "true";
    scoreContainer.textContent = "";
    ABCJS.renderAbc(scoreContainer, normalized, {
      responsive: "resize",
      add_classes: true,
      paddingtop: 15,
      paddingbottom: 15,
      paddingright: 15,
      paddingleft: 15,
    });
  }

  function renderFetchedAbcBlocks(scope) {
    scope.querySelectorAll(".abc-score[data-abc-src]").forEach(function (container) {
      if (container.dataset.abcRendered === "true" || container.dataset.abcLoading === "true") {
        return;
      }
      container.dataset.abcLoading = "true";
      var source = container.dataset.abcSrc;
      fetch(new URL(source, document.baseURI))
        .then(function (response) {
          if (!response.ok) {
            throw new Error("ABC request failed: " + response.status);
          }
          return response.text();
        })
        .then(function (abcText) {
          renderAbc(container, abcText);
        })
        .catch(function (error) {
          container.dataset.abcError = "true";
          container.textContent = "無法載入五線譜，請下載 ABC 原始檔。";
          console.warn(error);
        });
    });
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
      var scoreContainer = document.createElement("div");
      scoreContainer.className = "abc-score-container";
      wrapper.parentNode.insertBefore(scoreContainer, wrapper);
      renderAbc(scoreContainer, codeEl.textContent || "");
    });

    renderFetchedAbcBlocks(scope);
  }

  function renderCurrentDocument() {
    renderAllAbcBlocks(document);
  }

  // Material for MkDocs uses document$ for instant-navigation page changes.
  // Also render on the normal DOM lifecycle: on an initial page load,
  // document$ may already have emitted its first event before this script
  // subscribes.
  if (typeof document$ !== "undefined" && document$.subscribe) {
    document$.subscribe(function (body) {
      renderAllAbcBlocks(body);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", renderCurrentDocument);
  } else {
    renderCurrentDocument();
  }
})();
