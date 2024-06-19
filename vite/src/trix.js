import Trix from "trix";
import "trix/dist/trix.css";

var UPLOAD_URL = "/api/blobs/";

async function uploadAttachment(attachment) {
  const file = attachment.file;
  const formData = new FormData();
  formData.append("Content-Type", file.type);
  formData.append("file", file);

  const response = await fetch(UPLOAD_URL, {
    method: "POST",
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

//
// Trying to configure trix
//
// function updateActions() {
//   const editors = document.querySelectorAll("trix-editor");
//   const myAction = {
//     test: () => true,
//     perform: () => console.log("Hi!"),
//   };
//   editors.forEach((editor) => console.log(editor));
//   editors.forEach((editor) => Object.assign(editor.editorController.actions, {myAction}));
// }

export default function initTrix() {
  Trix.config.attachments.preview.caption.name = false;
  Trix.config.attachments.preview.caption.size = false;

  addEventListener("trix-attachment-add", function (event) {
    if (event.attachment.file) {
      uploadAttachment(event.attachment);
    }
  });

  // document.addEventListener("trix-initialize", updateActions);

  // document.addEventListener("trix-before-initialize", (event) => {
  //   console.log("trix-before-initialize");
  //   console.log(event);
  //   console.log("config", Trix.config);
  // });

  // document.addEventListener("trix-change", (event) => {
  //   console.log(event)
  // });
}
