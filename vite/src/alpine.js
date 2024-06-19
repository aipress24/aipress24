// Alpine
import Alpine from "alpinejs";

import Focus from "@alpinejs/focus";
import Persist from "@alpinejs/persist";

import setupToasts from "./alpine-toasts";

Alpine.plugin(Focus);
Alpine.plugin(Persist);

setupToasts(Alpine);

// import {AbilianTable} from "./table";

window.Alpine = Alpine;
