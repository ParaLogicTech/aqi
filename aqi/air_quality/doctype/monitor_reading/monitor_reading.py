# Copyright (c) 2023, ParaLogic and contributors
# For license information, please see license.txt

import frappe
from frappe import _, cint
from frappe.utils import get_datetime, round_down
from frappe.model.document import Document
from datetime import timedelta


class MonitorReading(Document):
	def validate(self):
		self.validate_duplicate()

	def on_update(self):
		clear_readings_cache()
		self.update_air_monitor()

	def on_trash(self):
		clear_readings_cache()
		self.update_air_monitor()

	def validate_duplicate(self):
		existing = frappe.db.get_value("Monitor Reading", {
			"air_monitor": self.air_monitor,
			"reading_dt": self.reading_dt,
			"name": ["!=", self.name]
		})

		if existing:
			frappe.throw(_("Monitor Reading for Air Monitor {0} at {1} already exists ({2})").format(
				frappe.bold(self.air_monitor),
				frappe.bold(self.get_formatted("reading_dt")),
				frappe.utils.get_link_to_form("Monitor Reading", existing)
			))

	def calculate_aqi(self):
		pass

	def determine_aqi_category(self):
		pass

	def update_air_monitor(self):
		air_monitor = frappe.get_doc("Air Monitor", self.air_monitor)
		air_monitor.set_first_last_reading(update=True)


def clear_readings_cache():
	cache_keys = ["latest_monitor_reading_dt"]
	for key in cache_keys:
		frappe.cache().delete_key(key)


def calculate_aqi(pollutant_value, pollutant_type):
	pollutant_precision = {
		"PM2.5": 1,
		"PM10": 0,
		"Ozone": 3,
		"CO": 1,
		"SO2": 0,
		"NO2": 0,
	}

	if pollutant_type not in pollutant_precision:
		frappe.throw(_("Invalid Pollutant Type"))

	precision = pollutant_precision[pollutant_type]
	pollutant_value = round_down(pollutant_value, precision)


@frappe.whitelist(allow_guest=True)
def get_latest_readings(for_datetime=None, window_minutes=60):
	from aqi.air_quality.doctype.air_monitor.air_monitor import _get_monitors

	if not for_datetime:
		for_datetime = get_latest_reading_dt()

	monitors = _get_monitors(filters={"first_reading_dt": ["<=", for_datetime]})
	monitors_map = {}
	for d in monitors:
		d.has_reading = False
		monitors_map[d.name] = d

	out = frappe._dict({
		"readings": [],
		"monitors": monitors_map,
		"latest_reading_dt": None,
		"from_dt": None,
		"to_dt": None
	})

	if not for_datetime:
		return out

	window_minutes = cint(window_minutes)
	if window_minutes <= 0:
		frappe.throw(_("window_minutes must be a positive integer"))
	if window_minutes > 1440:
		frappe.throw(_("window_minutes cannot be greater than 1440 minutes"))

	for_datetime = get_datetime(for_datetime)
	out.to_dt = for_datetime
	out.from_dt = out.to_dt - timedelta(minutes=window_minutes)

	readings = get_monitor_readings(out.from_dt, out.to_dt)
	if readings:
		out.latest_reading_dt = readings[0].reading_dt

	air_monitors_visited = set()
	for d in readings:
		if d.air_monitor not in air_monitors_visited:
			air_monitors_visited.add(d.air_monitor)
			out.readings.append(d)

	for monitor in air_monitors_visited:
		if monitors_map.get(monitor):
			monitors_map[monitor].has_reading = True

	return out


def get_monitor_readings(from_dt, to_dt):
	if not from_dt or not to_dt:
		frappe.throw(_("From Datetime and To Datetime is required"))

	args = frappe._dict({
		"from_dt": from_dt,
		"to_dt": to_dt,
	})

	return frappe.db.sql("""
		select r.name, r.reading_dt,
			r.air_monitor,
			r.pm_2_5, r.aqi_us, r.outdoor_pm_2_5, r.outdoor_aqi_us,
			r.temperature, r.relative_humidity, r.co2
		from `tabMonitor Reading` r
		inner join `tabAir Monitor` m on m.name = r.air_monitor
		where reading_dt between %(from_dt)s and %(to_dt)s and m.disabled = 0
		order by reading_dt desc
	""", args, as_dict=1)


@frappe.whitelist(allow_guest=True)
def get_latest_reading_dt():
	lastest_reading_dt = frappe.cache().get_value("latest_monitor_reading_dt", _get_latest_reading_dt)
	return get_datetime(lastest_reading_dt) if lastest_reading_dt else None


def _get_latest_reading_dt():
	latest = frappe.db.sql("""
		select reading_dt
		from `tabMonitor Reading`
		order by reading_dt desc
		limit 1
	""")

	return latest[0][0] if latest else None
