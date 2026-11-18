import Trix from "trix";
import "trix/dist/trix.css";

var UPLOAD_URL = "/api/trix_blobs/";

const YOUTUBE_EMBED_SRC_RE =
    /^https:\/\/(?:www\.)?youtube(?:-nocookie)?\.com\/embed\/[A-Za-z0-9_-]{11}(?:\?[A-Za-z0-9_=&%-]*)?$/;

const YOUTUBE_ALLOWED_IFRAME_ATTRS = [
    "src",
    "width",
    "height",
    "title",
    "frameborder",
    "allow",
    "allowfullscreen",
    "referrerpolicy",
    "loading",
];

/**
 * Extract an 11-character YouTube video ID from:
 * - an `<iframe ... src="...">` embed snippet,
 * - a `youtube.com/watch?v=...`, `youtu.be/...`, `youtube.com/embed/...`,
 *   `youtube-nocookie.com/embed/...`, `youtube.com/shorts/...` or `/live/...` URL,
 * - or a bare 11-char video ID.
 */
export function extractYouTubeVideoId(raw) {
    if (!raw || typeof raw !== "string") {
        return null;
    }
    const text = raw.trim();
    if (/^[A-Za-z0-9_-]{11}$/.test(text)) {
        return text;
    }
    const patterns = [
        /(?:youtube(?:-nocookie)?\.com\/(?:embed|shorts|live|v)\/|youtu\.be\/)([A-Za-z0-9_-]{11})/,
        /[?&]v=([A-Za-z0-9_-]{11})/,
    ];
    for (const pattern of patterns) {
        const match = text.match(pattern);
        if (match && match[1]) {
            return match[1];
        }
    }
    return null;
}

export function buildYouTubeIframeHtml(videoId) {
    return `<iframe width="560" height="315" src="https://www.youtube-nocookie.com/embed/${videoId}" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen loading="lazy"></iframe>`;
}

function configureTrixYouTubeSanitizer() {
    if (Trix.config?.dompurify) {
        const addTags = new Set(Trix.config.dompurify.ADD_TAGS || []);
        addTags.add("iframe");
        Trix.config.dompurify.ADD_TAGS = Array.from(addTags);

        const addAttr = new Set(Trix.config.dompurify.ADD_ATTR || []);
        for (const attr of YOUTUBE_ALLOWED_IFRAME_ATTRS) {
            addAttr.add(attr);
        }
        Trix.config.dompurify.ADD_ATTR = Array.from(addAttr);
    }

    const proto = Trix.HTMLSanitizer?.prototype;
    if (proto && !proto._youtubePatched) {
        const origElementIsForbidden = proto.elementIsForbidden;
        proto.elementIsForbidden = function (element) {
            if (
                element &&
                element.tagName &&
                element.tagName.toLowerCase() === "iframe"
            ) {
                const src = (element.getAttribute("src") || "").trim();
                if (YOUTUBE_EMBED_SRC_RE.test(src)) {
                    return false;
                }
            }
            return origElementIsForbidden.call(this, element);
        };

        const origSanitizeElement = proto.sanitizeElement;
        proto.sanitizeElement = function (element) {
            if (
                element &&
                element.tagName &&
                element.tagName.toLowerCase() === "iframe" &&
                Array.isArray(this.allowedAttributes)
            ) {
                for (const attr of YOUTUBE_ALLOWED_IFRAME_ATTRS) {
                    if (!this.allowedAttributes.includes(attr)) {
                        this.allowedAttributes.push(attr);
                    }
                }
            }
            return origSanitizeElement.call(this, element);
        };
        proto._youtubePatched = true;
    }
}

function injectTrixYouTubeStyles() {
    if (typeof document === "undefined" || document.getElementById("trix-youtube-styles")) {
        return;
    }
    const style = document.createElement("style");
    style.id = "trix-youtube-styles";
    style.textContent = `
        trix-toolbar .trix-button--icon-youtube::before {
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='2' y='4' width='20' height='16' rx='4'/%3E%3Cpolygon points='10 9 16 12 10 15 10 9' fill='%23000' stroke='none'/%3E%3C/svg%3E");
            top: 8%;
            bottom: 4%;
        }
        trix-editor figure.attachment--content iframe {
            max-width: 100%;
            border-radius: 0.375rem;
            margin: 0 auto;
            display: block;
        }
    `;
    document.head.appendChild(style);
}

function attachYouTubeToolbarToEditor(editorElement) {
    const toolbar = editorElement?.toolbarElement;
    if (!toolbar || toolbar.querySelector("[data-trix-action='x-youtube']")) {
        return;
    }

    const fileGroup =
        toolbar.querySelector(".trix-button-group--file-tools") ||
        toolbar.querySelector("[data-trix-button-group='file-tools']");
    const dialogsContainer =
        toolbar.querySelector(".trix-dialogs") ||
        toolbar.querySelector("[data-trix-dialogs]");
    if (!fileGroup || !dialogsContainer) {
        return;
    }

    const button = document.createElement("button");
    button.type = "button";
    button.className = "trix-button trix-button--icon trix-button--icon-youtube";
    button.setAttribute("data-trix-action", "x-youtube");
    button.setAttribute("title", "Insérer une vidéo YouTube");
    button.setAttribute("tabindex", "-1");
    button.textContent = "Vidéo YouTube";
    fileGroup.appendChild(button);

    const dialog = document.createElement("div");
    dialog.className = "trix-dialog trix-dialog--youtube";
    dialog.setAttribute("data-trix-dialog", "x-youtube");
    dialog.innerHTML = `
        <div class="trix-dialog__link-fields">
            <input
                type="text"
                name="youtube"
                class="trix-input trix-input--dialog"
                placeholder="Collez un code d'intégration (iframe) ou une URL YouTube…"
                aria-label="Code embed ou URL YouTube"
                disabled
            >
            <div class="trix-button-group">
                <input type="button" class="trix-button trix-button--dialog" data-youtube-insert value="Insérer la vidéo">
                <input type="button" class="trix-button trix-button--dialog" data-youtube-cancel value="Annuler">
            </div>
        </div>
    `;
    dialogsContainer.appendChild(dialog);

    const input = dialog.querySelector("input[name='youtube']");
    const insertBtn = dialog.querySelector("[data-youtube-insert]");
    const cancelBtn = dialog.querySelector("[data-youtube-cancel]");

    function closeDialog() {
        dialog.removeAttribute("data-trix-active");
        dialog.classList.remove("trix-active");
        input.value = "";
        input.setAttribute("disabled", "disabled");
        input.removeAttribute("data-trix-validate");
        input.classList.remove("trix-validate");
        button.removeAttribute("data-trix-active");
        button.classList.remove("trix-active");
    }

    function insertVideo() {
        const videoId = extractYouTubeVideoId(input.value);
        if (!videoId) {
            input.setAttribute("data-trix-validate", "");
            input.classList.add("trix-validate");
            input.focus();
            return;
        }
        const attachment = new Trix.Attachment({
            content: buildYouTubeIframeHtml(videoId),
            contentType: "video/youtube",
        });
        editorElement.editor.insertAttachment(attachment);
        closeDialog();
    }

    insertBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        insertVideo();
    });

    cancelBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        closeDialog();
    });

    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            e.stopPropagation();
            insertVideo();
        } else if (e.key === "Escape") {
            e.preventDefault();
            e.stopPropagation();
            closeDialog();
        }
    });
}

async function uploadAttachment(attachment) {
    const file = attachment.file;
    const formData = new FormData();
    formData.append("Content-Type", file.type);
    formData.append("file", file);

    const response = await fetch(UPLOAD_URL, {
        method: "POST",
        credentials: "same-origin",
        body: formData,
    });

    const responseData = await response.json();
    console.log(responseData);

    const attributes = {
        url: responseData.url,
        href: responseData.href + "?content-disposition=attachment",
    };
    console.log(attributes);
    attachment.setAttributes(attributes);
}

export default function initTrix() {
    Trix.config.attachments.preview.caption.name = false;
    Trix.config.attachments.preview.caption.size = false;

    configureTrixYouTubeSanitizer();
    injectTrixYouTubeStyles();

    addEventListener("trix-initialize", function (event) {
        attachYouTubeToolbarToEditor(event.target);
    });

    if (typeof document !== "undefined") {
        document.querySelectorAll("trix-editor").forEach((editorElement) => {
            attachYouTubeToolbarToEditor(editorElement);
        });
    }

    addEventListener("trix-attachment-add", function (event) {
        if (event.attachment.file) {
            uploadAttachment(event.attachment);
        }
    });
}
