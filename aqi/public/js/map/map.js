import Vue from "vue/dist/vue.js";
import { LMap, LTileLayer, LMarker } from "vue2-leaflet";
import MapView from "./MapView.vue"

Vue.component("l-map", LMap);
Vue.component("l-tile-layer", LTileLayer);
Vue.component("l-marker", LMarker);

frappe.provide('aqi');

aqi.make_map_view = function(container) {
	new Vue({
		el: container,
		render: h => h(MapView)
	});
}
