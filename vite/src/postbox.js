// Temp workaround for Postbox issue
window.PostBox = function () {
  return {
    isOpen: false,

    open() {
      this.isOpen = true;
    },

    close() {
      this.isOpen = false;
    },

    toggle() {
      this.isOpen = !this.isOpen;
    },

    submit() {
      const text = document.getElementById("text-field").innerText;
      const field = document.getElementById("hidden-text-field");
      field.value = text;
    },
  };
};
