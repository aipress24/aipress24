// Alpine
import Alpine from "alpinejs";

import Focus from "@alpinejs/focus";
import Persist from "@alpinejs/persist";
import Validate from "@colinaut/alpinejs-plugin-simple-validate";

import setupToasts from "./alpine-toasts";

Alpine.plugin(Focus);
Alpine.plugin(Persist);
Alpine.plugin(Validate);

setupToasts(Alpine);

// import {AbilianTable} from "./table";

window.Alpine = Alpine;
