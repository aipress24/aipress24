/* Utils to keep alpha can on PNG images. */
(function (window) {
    "use strict";

    /**
     * Detect PNG image.
     * @param {string|File|null} fileOrType
     * @returns {boolean}
     */
    function isPngImage(fileOrType) {
        if (!fileOrType) return false;
        if (typeof fileOrType === "string") {
            return (
                fileOrType.includes("png") ||
                fileOrType.toLowerCase().endsWith(".png")
            );
        }
        if (fileOrType && fileOrType.type) {
            return fileOrType.type === "image/png";
        }
        if (fileOrType && fileOrType.name) {
            return fileOrType.name.toLowerCase().endsWith(".png");
        }
        return false;
    }

    /**
     * Get canvas content, keeping transparency
     * @param {Object} cropper - Cropper instance
     * @param {Object} [options={}]
     * @param {string|File|null} [fileOrType=null]
     * @returns {HTMLCanvasElement|null}
     */
    function getCroppedCanvas(cropper, options, fileOrType) {
        if (!cropper || typeof cropper.getCroppedCanvas !== "function")
            return null;

        options = options || {};
        var isPng = isPngImage(fileOrType);
        var defaultFillColor = isPng ? "transparent" : "#ffffff";

        var canvasOptions = Object.assign(
            {
                fillColor: defaultFillColor,
                imageSmoothingEnabled: true,
                imageSmoothingQuality: "high",
            },
            options
        );

        return cropper.getCroppedCanvas(canvasOptions);
    }

    /**
     * Export canvas, either PNG or JPEG
     * @param {Object} cropper
     * @param {Object} [options={}]
     * @param {string|File|null} [fileOrType=null]
     * @returns {string|null}
     */
    function getCroppedDataURL(cropper, options, fileOrType) {
        var canvas = getCroppedCanvas(cropper, options, fileOrType);
        if (!canvas) return null;

        var isPng = isPngImage(fileOrType);
        return isPng
            ? canvas.toDataURL("image/png")
            : canvas.toDataURL("image/jpeg", 0.9);
    }

    /**
     * Export canvas as blob
     * @param {Object} cropper
     * @param {Object} [options={}]
     * @param {string|File|null} [fileOrType=null]
     * @param {Function} callback
     */
    function getCroppedBlob(cropper, options, fileOrType, callback) {
        var canvas = getCroppedCanvas(cropper, options, fileOrType);
        if (!canvas) {
            if (typeof callback === "function") callback(null);
            return;
        }

        var isPng = isPngImage(fileOrType);
        var mimeType = isPng ? "image/png" : "image/jpeg";
        var quality = isPng ? undefined : 0.9;
        canvas.toBlob(callback, mimeType, quality);
    }

    window.isPngImage = isPngImage;
    window.getCroppedCanvas = getCroppedCanvas;
    window.getCroppedDataURL = getCroppedDataURL;
    window.getCroppedBlob = getCroppedBlob;
})(typeof window !== "undefined" ? window : this);
