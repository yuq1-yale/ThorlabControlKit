import tkinter as tk
from tkinter import ttk
from ctypes import (
    c_double, c_int16, c_uint32,
    byref, create_string_buffer, c_bool, c_char_p, c_int
)
from PowerMeterControl.TLPMX import TLPMX, TLPM_DEFAULT_CHANNEL
import time
import statistics
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk


class SolidButton(tk.Button):
    """A Button with a solid black border."""
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(
            highlightthickness=1,
            highlightbackground='black',
            bd=1,            # 1px border
            relief='raised',
            padx=10,
            pady=5
        )
        self.bind("<Enter>", lambda e: self.configure(relief='groove'))
        self.bind("<Leave>", lambda e: self.configure(relief='raised'))


class PowerMeterGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.tlPM = TLPMX()
        self.title("Power Meter Control")
        self.option_add("*Font", "Arial 12")
        self.status = 0  # 0: disconnected, 1: connected
        self.time_window = 1000.0  # default time window in seconds
        self.plot_time_window = 10.0  # default plot window in seconds
        self.wavelength = 532.0  # default wavelength in nm
        self.auto_power_flag = 0  # flag for auto power range
        self.unit = 1E-6  # default unit in uW
        self.plot_power_min_inW = 18e-6  # default min power in Watts
        self.plot_power_max_inW = 20e-6  # default max power in
        self.plot_power_min = self.plot_power_min_inW / self.unit  # default min power for plot
        self.plot_power_max = self.plot_power_max_inW / self.unit  # default max power for plot
        self.times = []
        self.powers = []
        
        self.start_time = None
        self.measure_interval_ms = 100

        self._create_widgets()
        self._layout_widgets()

    def _create_widgets(self):
        # ─── CONNECTION FRAME ───────────────────────────────
        self.conn_frame = tk.LabelFrame(
            self,
            text="Connection ●",
            fg="red",
            labelanchor='nw',   # dot sits in the top‐left
            padx=10,
            pady=5
        )
        # Two solid‐border buttons
        self.btn_scan       = SolidButton(self.conn_frame, text="Scan", command=self._on_scan)

        # a select combobox for selecting the device
        self.device_combo = ttk.Combobox(self.conn_frame, state='readonly')
        self.device_combo['values'] = []

        self.btn_connect    = SolidButton(self.conn_frame, text="Connect",    command=self._on_connect)
        self.btn_disconnect = SolidButton(self.conn_frame, text="Disconnect", state='disabled', command=self._on_disconnect)
        self.lbl_fresh_rate = tk.Label(self.conn_frame, text="Refresh Rate (ms):", anchor='w', width=15)
        self.lbl_fresh_rate_value = tk.Label(self.conn_frame, text=str(self.measure_interval_ms), anchor='w', width=5)
        
        # ----Power Show Frame ──────────────────────────────
        self.power_frame = tk.LabelFrame(
            self,
            text="Power Show",
            padx=10,
            pady=5
        )
        self.void = tk.Label(self.power_frame, text="  ", font=("Arial", 24), width=5)  # placeholder
        self.lbl_power_val = tk.Label(self.power_frame, text="0.0", font=("Arial", 24), anchor='e', width=8)
        self.lbl_unit = tk.Label(self.power_frame, text="uW", font=("Arial", 16), anchor='w', width=3)
        self.btn_unit_uw = SolidButton(self.power_frame, text="uw", command=lambda: self._change_unit("uW"))
        self.btn_unit_mw = SolidButton(self.power_frame, text="mw", command=lambda: self._change_unit("mW"))

        # ---- Draw the graph area ──────────────────────────────
        self.canvas_graph = tk.Canvas(self.power_frame, bg='white', width=800, height=400)
        self.fig = Figure(figsize=(5, 3), dpi=100)
        self.ax = self.fig.add_subplot(111) # Add a subplot to the figure
        self.ax.set_xlim(0, self.plot_time_window)
        self.ax.set_ylim(self.plot_power_min, self.plot_power_max)
        self.ax.grid(True)
        self.ax.plot()

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.canvas_graph)
        self.canvas.draw()

        self.lbl_time_range = tk.Label(self.power_frame, text="Time Range (s): ", anchor='w', width=15)
        self.ent_time_range = tk.Entry(self.power_frame, width=7, justify='right')
        self.btn_time_range = SolidButton(self.power_frame, text="Set", command=self._set_time_range)
        # holdplace value for time range entry
        self.ent_time_range.insert(0, str(self.plot_time_window))

        self.lbl_power_range = tk.Label(self.power_frame, text="Power Range (uW): ", anchor='w', width=15)
        self.ent_power_range_min = tk.Entry(self.power_frame, width=7, justify='right')
        self.ent_power_range_max = tk.Entry(self.power_frame, width=7, justify='right')
        # run self._set_power_range() and update the auto power flag when clicked
        self.btn_power_range = SolidButton(self.power_frame, text="Set", command=self.on_set_power_range_click, bg='lightgreen')
        self.btn_power_range.bind("<Button-1>", lambda e: setattr(self, 'auto_power_flag', 0))  # reset auto power flag on manual set
        # holdplace values for power range entries
        self.ent_power_range_min.insert(0, f"{self.plot_power_min:0.2f}")
        self.ent_power_range_max.insert(0, f"{self.plot_power_max:0.2f}")
        self.btn_autoset = SolidButton(self.power_frame, text="Auto Set", command=self.on_autoset_click, bg='grey')
        self.btn_power_range.bind("<Button-1>", lambda e: self.btn_power_range.config(bg='lightgreen'))
        self.btn_power_range.bind("<Button-1>", lambda e: self.btn_autoset.config(bg='grey'))
        # ---- Wavelength Selection ──────────────────────────────
        self.wavelength_frame = tk.LabelFrame(
            self,
            text="Wavelength Selection",
            padx=10,
            pady=5
        )
        self.lbl_wavelength = tk.Label(self.wavelength_frame, text="Wavelength (nm):", anchor='w', width=15)
        self.lbl_wavelength_value = tk.Label(self.wavelength_frame, text=f"{self.wavelength:0.2f}", anchor='w', width=6)
        self.ent_wavelength = tk.Entry(self.wavelength_frame, width=7, justify='right')
        self.btn_set_wavelength = SolidButton(self.wavelength_frame, text="Set", command=self._set_wavelength)

        self.default_wavelength = [532, 775, 1064, 1550] # default wavelengths in nm
        # quick button for default wavelengths
        self.btn_wavelengths = []  
        
        for wl in self.default_wavelength:
            btn = SolidButton(self.wavelength_frame, text=f"{wl} nm", command=lambda w=wl: self.ent_wavelength.delete(0, tk.END) or self.ent_wavelength.insert(0, f"{w:0.2f}"))
            self.btn_wavelengths.append(btn)
    def _layout_widgets(self):
        # ─── CONNECTION FRAME ───────────────────────────────
        self.conn_frame.pack(fill='x', padx=10, pady=(10, 5))
        # Pack them side by side
        self.btn_scan.pack(side='left', padx=5)
        self.device_combo.pack(side='left', padx=5, fill='x', expand=True)
        self.device_combo.bind("<<ComboboxSelected>>", lambda e: self._on_disconnect() if self.status == 1 else None)  # auto connect on selection
        # self.device_combo.bind("<<ComboboxSelected>>", lambda e: self._on_connect() if self.status == 0 else None)  # auto connect on selection
        for btn in (self.btn_connect, self.btn_disconnect):
            btn.pack(side='left', padx=5)
        
        self.lbl_fresh_rate.pack(side='left', padx=5)
        self.lbl_fresh_rate_value.pack(side='left', padx=5)

        # ---- Power Show Frame ──────────────────────────────
        self.power_frame.pack(fill='x', padx=10, pady=(5, 10))
        self.void.grid(row=0, column=0, padx=10, pady=10)
        self.lbl_power_val.grid(row=0, column=1, columnspan=3, padx=10, pady=10)
        self.lbl_unit.grid(row=0, column=4, padx=10, pady=10)
        self.btn_unit_uw.grid(row=0, column=5, padx=5)
        self.btn_unit_mw.grid(row=0, column=6, padx=5)

        # ---- Draw the graph area ──────────────────────────────
        self.canvas_graph.grid(row=1, column=0, columnspan=7, padx=10, pady=10)
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=1)

        self.lbl_time_range.grid(row=2, column=0, padx=10, pady=5)
        self.ent_time_range.grid(row=2, column=2, padx=15, pady=5)
        self.btn_time_range.grid(row=2, column=3, padx=5, pady=5)

        self.lbl_power_range.grid(row=3, column=0, padx=10, pady=5)
        self.ent_power_range_min.grid(row=3, column=1, padx=15, pady=5)
        self.ent_power_range_max.grid(row=3, column=2, padx=15, pady=5)
        self.btn_power_range.grid(row=3, column=3, padx=5, pady=5)
        self.btn_autoset.grid(row=3, column=4, padx=5, pady=5)

        # ---- Wavelength Selection ──────────────────────────────
        self.wavelength_frame.pack(fill='x', padx=10, pady=(5, 10))
        self.lbl_wavelength.grid(row=0, column=0, padx=10, pady=5)
        self.lbl_wavelength_value.grid(row=0, column=1, padx=10, pady=5)
        self.ent_wavelength.grid(row=0, column=2, padx=10, pady=5)
        self.btn_set_wavelength.grid(row=0, column=3, padx=5, pady=5)
        for i, btn in enumerate(self.btn_wavelengths):
            btn.grid(row=1, column=i+1, padx=5, pady=5)

    # ------CONNECTION ---------------------------------------------
    def _on_scan(self):
        deviceCount = c_uint32()
        self.tlPM.findRsrc(byref(deviceCount))
        print("Number of found devices: " + str(deviceCount.value))
        resourceName = create_string_buffer(1024)
        self.resnamelist = []  # to store resource names
        for i in range(0, deviceCount.value):
            self.tlPM.getRsrcName(c_int(i), resourceName)
            print("Resource name of device", i, ":", c_char_p(resourceName.raw).value)
            self.resnamelist.append(c_char_p(resourceName.raw).value.decode('utf-8'))
        # the values of the combobox is the name between last :: and second last ::
        self.device_combo['values'] = [name.split("::")[-2] for name in self.resnamelist]
        if deviceCount.value > 0:
            self.device_combo.current(0)

    def _on_connect(self):
        print("Connecting")
        if self.status == 0:
            try:
                self._connect_device()
                self.status = 1
                self.btn_connect.config(state='disabled')
                self.btn_disconnect.config(state='normal')
                self.conn_frame.config(text="Connection ●", fg="green")
                self._measure()
            except Exception as e:
                print(f"Error connecting: {e}")

        # here you’d enable Home & Disconnect, disable Connect, etc.
    
    def _on_disconnect(self):
        print("Disconnecting")
        # stop the measurement loop
        if hasattr(self, "_after_id"):
            self.after_cancel(self._after_id)
            del self._after_id
        self._disconnect_device()
        self.status = 0
        self.btn_connect.config(state='normal')
        self.btn_disconnect.config(state='disabled')
        self.conn_frame.config(text="Connection ●", fg="red")

    def _connect_device(self):
        # device number
        device_number_from_combo = self.device_combo.current()
        if device_number_from_combo < 0:
            print("No device selected")
            return
        print("Selected device:", self.resnamelist[device_number_from_combo])
        resourceName = create_string_buffer(1024)
        self.tlPM.getRsrcName(c_int(device_number_from_combo), resourceName)
        self.tlPM.open(resourceName, c_bool(True), c_bool(True))
        self.times.clear()
        self.powers.clear()
        time.sleep(2)  # allow time for connection
        self.tlPM.setPowerAutoRange(c_int16(1), TLPM_DEFAULT_CHANNEL)
        self.tlPM.setPowerUnit(c_int16(0), TLPM_DEFAULT_CHANNEL)
        self.start_time = time.time()
    
    def _disconnect_device(self):
        if hasattr(self, "tlPM"):
            self.tlPM.close()

    # ------UNIT CHANGE ---------------------------------------------
    def _change_unit(self, unit):
        if self.status == 1:
            if unit == "uW":
                self.unit = 1E-6  # microWatt
                self.lbl_power_range.config(text=f"Power Range (uW): ")
            elif unit == "mW":
                self.unit = 1E-3  # milliWatt
                self.lbl_power_range.config(text=f"Power Range (mW): ")
            # Update the power range labels
            self.plot_power_min = self.plot_power_min_inW / self.unit  # default min power for plot
            self.plot_power_max = self.plot_power_max_inW / self.unit  # default max power for plot
            # change the holdplace values for power range entries
            self.ent_power_range_min.delete(0, tk.END)
            self.ent_power_range_min.insert(0, f"{self.plot_power_min:0.2f}")
            self.ent_power_range_max.delete(0, tk.END)
            self.ent_power_range_max.insert(0, f"{self.plot_power_max:0.2f}")
            print(f"Power unit set to {unit}")
            self.lbl_unit.config(text=unit)
        else:
            print("Device not connected - change unit failed")

    
    # ------MEASUREMENT ---------------------------------------------
    def _measure(self):
        if self.status == 1:
            try:
                power = c_double()
                self.tlPM.measPower(byref(power), TLPM_DEFAULT_CHANNEL)
                val = power.value / self.unit
                self.lbl_power_val.config(text=f"{val:0.4f}")
                elapsed = time.time() - self.start_time
                # print(f"Measured Power: {power.value} W")
                self.times.append(elapsed)
                self.powers.append(power.value)
                T = self.time_window
                while self.times and self.times[0] < elapsed - T:
                    self.times.pop(0)
                    self.powers.pop(0)
                self._update_fig()
                if len(self.times) % 5 == 0:  # update every 5 measurements
                    self.measure_interval_ms_real = (self.times[-1] - self.times[-21]) / 20 * 1000
                    self.lbl_fresh_rate_value.config(text=str(self.measure_interval_ms_real))
                # after 20 measurements, auto set the power range
                if len(self.times) == 21:
                    self._on_autoset_power()
                if self.auto_power_flag == 1 and len(self.times) % 40 == 0:
                    self._on_autoset_power()

            except Exception as e:
                pass
        else:
            print("Device not connected - measurement failed")
            return None
        self._after_id = self.after(self.measure_interval_ms, self._measure)
        
    def _update_fig(self):
        self.ax.clear()
        self.ax.grid(True)

        if not self.times:
            return

        # Use the last `plot_time_window` seconds of data
        current_time = self.times[-1]
        t_min = max(0, current_time - self.plot_time_window - 1)  # 1 second buffer

        # Filter points within the time window
        self.times_filtered = [t for t in self.times if t >= t_min]
        self.powers_filtered = self.powers[-len(self.times_filtered):]
        self.powers_unit = [p / self.unit for p in self.powers_filtered]

        self.ax.set_xlim(0, self.plot_time_window)
        self.ax.set_ylim(self.plot_power_min, self.plot_power_max)
        self.ax.plot([t - t_min for t in self.times_filtered], self.powers_unit, label="Power", color='blue')
        self.ax.legend()
        self.canvas.draw()
    
    def _set_time_range(self):
        try:
            T = float(self.ent_time_range.get())
            if T <= 0:
                raise ValueError("Time range must be positive")
        except ValueError:
            print("Invalid time range input")
            return
        
        self.plot_time_window = T
        self._update_fig()
        print(f"Time window set to {T} seconds")

    def _set_power_range(self):
        try:
            p_min = float(self.ent_power_range_min.get())
            p_max = float(self.ent_power_range_max.get())
            if p_min >= p_max:
                raise ValueError("Minimum power must be less than maximum power")
        except ValueError:
            print("Invalid power range input")
            return
        self.plot_power_min_inW = p_min * self.unit
        self.plot_power_max_inW = p_max * self.unit
        self.plot_power_min = p_min
        self.plot_power_max = p_max
        self.ax.set_ylim(self.plot_power_min, self.plot_power_max)
        self._update_fig()
        print(f"Power range set to {p_min} - {p_max} {self.lbl_unit.cget('text')}")

    def on_autoset_click(self, event=None):
        self.auto_power_flag = 1
        self.btn_autoset.config(bg='lightgreen')
        self.btn_power_range.config(bg='grey')
        self._on_autoset_power()

    def on_set_power_range_click(self, event=None):
        self.auto_power_flag = 0
        self.btn_power_range.config(bg='lightgreen')
        self.btn_autoset.config(bg='grey')
        self._set_power_range()

    def _on_autoset_power(self):
        if self.status == 1:
            try:
                # set the auto-range by previous self.powers and self.times in plot_time_window
                if self.powers:
                    delta_power = max(self.powers_unit) - min(self.powers_unit)
                    p_min = min(self.powers_unit) - delta_power
                    p_max = max(self.powers_unit) + delta_power
                    p_min = max(0, p_min)  # ensure min is not negative
                    self.ent_power_range_min.delete(0, tk.END)
                    self.ent_power_range_min.insert(0, f"{p_min:0.2f}")
                    self.ent_power_range_max.delete(0, tk.END)
                    self.ent_power_range_max.insert(0, f"{p_max:0.2f}")
                    self.plot_power_min = p_min
                    self.plot_power_max = p_max
                    self._set_power_range()
            except Exception as e:
                print(f"Error in autoset: {e}")
        else:
            print("Device not connected - autoset failed")
            return None
        
    def _get_wavelength(self):
        # get wavelength from equipment
        if self.status == 1:
            wavelength = c_double()
            self.tlPM.getWavelength(byref(wavelength), TLPM_DEFAULT_CHANNEL)
            return wavelength.value
        else:
            print("Device not connected - get wavelength failed")
            return None
    
    def _set_wavelength(self):
        try:
            wavelength = float(self.ent_wavelength.get())
            if wavelength <= 0:
                raise ValueError("Wavelength must be positive")
        except ValueError:
            print("Invalid wavelength input")
            return
        
        self.wavelength = wavelength
        self.tlPM.setWavelength(c_double(wavelength), TLPM_DEFAULT_CHANNEL)
        self.lbl_wavelength_value.config(text=f"{wavelength:0.2f}")
        print(f"Wavelength set to {wavelength} nm")
        
if __name__ == "__main__":
    PowerMeterGUI().mainloop()
