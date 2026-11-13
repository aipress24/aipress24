import "./css/styles.css";

import "@/alpine.js";
import "@/htmx.js";
import "@/quill.js";
import "@/postbox.js";
import "@/trix.js";
import "@/cropperjs.js";

import "@/vendor/alpine-components.js";

import setupLivewire from "@/livewire.js";
import initTrix from "@/trix";
import imageViewer from "@/image-upload";

import 'flowbite';

import Chart from "chart.js/auto";
import Choices from "choices.js";

// Export in the global namesapce
window.imageViewer = imageViewer;
// Templates call these from inline scripts and Alpine `init()` hooks.
window.Chart = Chart;
window.Choices = Choices;

setupLivewire();
initTrix();
Alpine.start();
