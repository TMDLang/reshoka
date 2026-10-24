(function () {
  function initLuckySong(root) {
    var card = (root || document).querySelector("[data-lucky-song]");
    if (!card || card.dataset.luckySongReady === "true") {
      return;
    }

    var button = card.querySelector("[data-lucky-song-button]");
    var result = card.querySelector("[data-lucky-song-result]");
    if (!button || !result) {
      return;
    }

    card.dataset.luckySongReady = "true";
    var songsPromise = fetch(new URL("data/songs.json", document.baseURI))
      .then(function (response) {
        if (!response.ok) {
          throw new Error("Unable to load song index");
        }
        return response.json();
      });

    button.addEventListener("click", function () {
      button.disabled = true;
      songsPromise
        .then(function (songs) {
          if (!songs.length) {
            throw new Error("Song index is empty");
          }
          var song = songs[Math.floor(Math.random() * songs.length)];
          result.textContent = '';
          var link = document.createElement("a");
          link.href = song.url;
          link.textContent =
            song.title + " · " + song.collection + " · " + song.volume;
          result.appendChild(document.createTextNode(" "));
          result.appendChild(link);
        })
        .catch(function () {
          result.textContent = "目前無法載入曲目索引，請稍後再試。";
        })
        .finally(function () {
          button.disabled = false;
        });
    });
  }

  if (typeof document$ !== "undefined" && document$.subscribe) {
    document$.subscribe(function (body) {
      initLuckySong(body);
    });
  } else {
    document.addEventListener("DOMContentLoaded", function () {
      initLuckySong(document);
    });
  }
})();
