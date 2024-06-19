function setupToasts(Alpine) {
  Alpine.store("toasts", {
    counter: 0,

    list: [],

    createToast(message, type = "info") {
      const index = this.list.length;
      const totalVisible =
        this.list.filter((toast) => {
          return toast.visible;
        }).length + 1;
      const toast = {
        id: this.counter++,
        message,
        type,
        visible: true,
      };
      this.list.push(toast);
      setTimeout(() => {
        this.destroyToast(index);
      }, 2000 * totalVisible);
    },

    destroyToast(index) {
      this.list[index].visible = false;
    },
  });

  document.body.addEventListener("showToast", function (e) {
    const message = e.detail.value;
    Alpine.store("toasts").createToast(message);
  });

  if (window.toasts) {
    for (let i = 0; i < window.toasts.length; i++) {
      Alpine.store("toasts").createToast(window.toasts[i]);
    }
  }
}

export default setupToasts;
