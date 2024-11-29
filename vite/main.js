import "./css/styles.css";

import "@/alpine.js";
import "@/htmx.js";
import "@/quill.js";
import "@/postbox.js";
import "@/trix.js";

import "@/vendor/alpine-components.js";

import setupLivewire from "@/livewire.js";
import initTrix from "@/trix";
import imageViewer from "@/image-upload";

import 'flowbite';

// Export in the global namesapce
window.imageViewer = imageViewer;

setupLivewire();
initTrix();
Alpine.start();
