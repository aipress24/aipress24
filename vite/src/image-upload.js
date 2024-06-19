// See https://vemto.app/blog/how-to-create-an-image-upload-viewer-with-alpinejs

function imageViewer() {
  return {
    imageUrl: "",

    fileChosen(event) {
      this.fileToDataUrl(event, (src) => (this.imageUrl = src));
    },

    fileToDataUrl(event, callback) {
      if (!event.target.files.length) return;

      const file = event.target.files[0];
      const reader = new FileReader();

      reader.readAsDataURL(file);
      reader.onload = (e) => callback(e.target.result);
    },
  };
}

export default imageViewer;
