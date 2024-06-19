import Livewire from "@/vendor/livewire";

function setupLivewire() {
  if (window.livewire) {
    console.warn(
      "Livewire: It looks like Livewire's @livewireScripts JavaScript assets have already been loaded. Make sure you aren't loading them twice."
    );
  }

  window.livewire = new Livewire();

  window.livewire.devTools(true);
  window.Livewire = window.livewire;
  window.livewire_app_url = "";
  window.livewire_token = "BDlVCEjah2zzrisLmImBGuIWIB2YNPP36Y5IFh4k";

  /* Make sure Livewire loads first. */
  if (window.Alpine) {
    /* Defer showing the warning so it doesn't get buried under downstream errors. */
    document.addEventListener("DOMContentLoaded", function () {
      setTimeout(function () {
        console.warn(
          "Livewire: It looks like AlpineJS has already been loaded. Make sure Livewire's scripts are loaded before Alpine.\\n\\n Reference docs for more info: http://laravel-livewire.com/docs/alpine-js"
        );
      });
    });
  }

  /* Make Alpine wait until Livewire is finished rendering to do its thing. */
  window.deferLoadingAlpine = function (callback) {
    window.addEventListener("livewire:load", function () {
      callback();
    });
  };

  let started = false;

  window.addEventListener("alpine:initializing", function () {
    if (!started) {
      window.livewire.start();

      started = true;
    }
  });

  document.addEventListener("DOMContentLoaded", function () {
    if (!started) {
      window.livewire.start();

      started = true;
    }
  });
}

export default setupLivewire;
