import Cropper from 'cropperjs';
import 'cropperjs/dist/cropper.css';

// Cropper measures its container once, when the image is ready. A container
// still hidden at that moment (an Alpine `x-show` that has not shown yet)
// measures nothing, and Cropper falls back to its 200×100 minimum. Measure
// again whenever the container's size changes.
class ResizingCropper extends Cropper {
  constructor(element, options) {
    super(element, options);
    this.sizeObserver = new ResizeObserver(() => {
      if (this.ready && this.container.offsetWidth > 0) {
        this.resize();
      }
    });
    this.sizeObserver.observe(element.parentNode);
  }

  destroy() {
    this.sizeObserver.disconnect();
    return super.destroy();
  }
}

window.Cropper = ResizingCropper;
