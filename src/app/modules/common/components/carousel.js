// TODO: make it a component (currently not used!)
document.addEventListener('alpine:init', () => {
  Alpine.data('carousel', (carouselData = { slides: [] }) => ({
    slides: carouselData.slides,
    currentSlideIndex: 1,
    previous() {
      if (this.currentSlideIndex > 1) {
        this.currentSlideIndex = this.currentSlideIndex - 1
      } else {
        // If it's the first slide, go to the last slide
        this.currentSlideIndex = this.slides.length
      }
    },
    next() {
      if (this.currentSlideIndex < this.slides.length) {
        this.currentSlideIndex = this.currentSlideIndex + 1
      } else {
        // If it's the last slide, go to the first slide
        this.currentSlideIndex = 1
      }
    },
  }))
});
