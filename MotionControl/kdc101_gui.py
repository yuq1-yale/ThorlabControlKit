import os
import sys
import json
import time
import tkinter as tk
from ctypes import *
import tkinter.messagebox as mb

status = 1
os.add_dll_directory(r"C:\Program Files\Thorlabs\Kinesis")
lib: CDLL = cdll.LoadLibrary(
    "Thorlabs.MotionControl.KCube.DCServo.dll"
)
serial_num = c_char_p(b"27007518")
STEPS_PER_REV = c_double(34555)  # for the PRM1-Z8
gbox_ratio = c_double(1.0)
pitch = c_double(1.0)
pos_min = 0
pos_max = 25


POSITIONS_FILE = 'positions.json'

def update_position(new_pos_real):
    new_pos_dev = c_int()
    lib.CC_GetDeviceUnitFromRealValue(
        serial_num, c_double(new_pos_real),
        byref(new_pos_dev), 0
    )
    lib.CC_SetMoveAbsolutePosition(serial_num, new_pos_dev)
    lib.CC_MoveAbsolute(serial_num)
    # time.sleep(0.25)



class DashedEntry(tk.Frame):
    def __init__(self, master=None, width=80, height=24, **kwargs):
        super().__init__(master)
        self.canvas = tk.Canvas(
            self, width=width, height=height,
            highlightthickness=0, bd=0, bg=self['bg']
        )
        self.canvas.pack()
        self.canvas.create_rectangle(
            1, 1, width-1, height-1,
            dash=(3, 3), outline='black'
        )
        self.entry = tk.Entry(self.canvas, bd=0, **kwargs)
        self.canvas.create_window(
            width//2, height//2, window=self.entry,
            width=width-6, height=height-6
        )

    def get(self):
        return self.entry.get()


class SolidButton(tk.Button):
    """A Button with a solid black border."""
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(
            highlightthickness=1,
            highlightbackground='black',
            bd=1,            # 1px border
            relief='raised',
            padx=8,
            pady=4
        )
        self.bind("<Enter>", lambda e: self.configure(relief='groove'))
        self.bind("<Leave>", lambda e: self.configure(relief='raised'))

def load_state(num_slots, default_current=10.0):
    if os.path.exists(POSITIONS_FILE):
        try:
            with open(POSITIONS_FILE, 'r') as f:
                data = json.load(f)
            current = float(data.get('current_pos', default_current))
            slots = data.get('slots', [0.0] * num_slots)
            slots = (slots + [0.0] * num_slots)[:num_slots]
            return current, [float(v) for v in slots]
        except Exception:
            pass
    return default_current, [0.0] * num_slots


def save_state(current_pos, slots):
    data = {
        'current_pos': current_pos.get(),
        'slots': [sv.get() for sv in slots]
    }
    try:
        with open(POSITIONS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print("Error saving positions:", e)

def build_gui():
    root = tk.Tk()
    root.title("Position Controller")

    # --- Shared state ---
    num_slots = 4
    init_current, init_slots = load_state(num_slots)
    current_pos = tk.DoubleVar(value=init_current)
    slots = [tk.DoubleVar(value=v) for v in init_slots]

    disp_set = tk.StringVar()
    disp_dev = tk.StringVar()
    def _upd_set(*args):
        disp_set.set(f"{current_pos.get():.4f}")
    def _upd_dev(*args):
        disp_dev.set(f"{dev_var.get():.4f}")
    current_pos.trace_add("write", _upd_set)
    dev_var = tk.DoubleVar(value=0.0)
    homed_var = tk.BooleanVar(value=False)
    dev_var.trace_add("write", _upd_dev)    
    _upd_set()
    _upd_dev()

    def safe_set_current(v):
        if v < pos_min or v > pos_max:
            mb.showwarning("Out of Range",
                            f"Position must be between {pos_min} and {pos_max} mm")
        else:
            current_pos.set(v)

    def persist():
        save_state(current_pos, slots)

    # --- Top bar: Connect / Home / Disconnect (boxed) ---
    conn_frame = tk.LabelFrame(root, text="Connection ●", padx=10, pady=5, fg="red")
    conn_frame.pack(fill='x', padx=10, pady=(10, 5))

    btn_connect    = SolidButton(conn_frame, text="Connect")
    btn_home       = SolidButton(conn_frame, text="Home",    state='disabled')
    btn_disconnect = SolidButton(conn_frame, text="Disconnect", state='disabled')

    btn_connect.pack(side='left', padx=5)
    btn_home.pack(   side='left', padx=5)
    btn_disconnect.pack(side='left', padx=5)

    def do_connect():
        global status
        if lib.TLI_BuildDeviceList() == 0:
            status = lib.CC_Open(serial_num)
        if status == 0:
            print("→ Connected")
            btn_connect.config(state='disabled')
            btn_home.config(state='normal')
            btn_disconnect.config(state='normal')
            conn_frame.config(text="Connection ●", fg="green")
            lib.CC_StartPolling(serial_num, c_int(200))
            lib.CC_SetMotorParamsExt(
                serial_num, STEPS_PER_REV, gbox_ratio, pitch
            )
            time.sleep(0.1)
            lib.CC_RequestPosition(serial_num)
            real_val = c_double()
            unit = lib.CC_GetPosition(serial_num)
            lib.CC_GetRealValueFromDeviceUnit(
                serial_num, c_int(unit), byref(real_val), 0
            )
            safe_set_current(real_val.value)

    def do_home():
        print("→ Homing...")
        lib.CC_Home(serial_num)
        safe_set_current(0.0)

    def do_disconnect():
        global status
        print("→ Disconnected")
        status = 1
        btn_connect.config(state='normal')
        btn_home.config(   state='disabled')
        btn_disconnect.config(state='disabled')
        conn_frame.config(text="Connection ●", fg="red")
        lib.CC_Close(serial_num)

    btn_connect.config(   command=do_connect)
    btn_home.config(      command=do_home)
    btn_disconnect.config(command=do_disconnect)

    # --- Section 1: Current & Device Position ---
    sec1 = tk.LabelFrame(root, text="Positions", padx=10, pady=10)
    sec1.pack(fill='x', padx=10, pady=(5, 5))

    tk.Label(sec1, text="Set Position:").grid(row=0, column=0, sticky='w')
    tk.Label(sec1, textvariable=disp_set,
            font=('TkDefaultFont', 18)).grid(row=0, column=1, padx=(5,20))

    tk.Label(sec1, text="Device Position:").grid(row=1, column=0, sticky='w')
    tk.Label(sec1, textvariable=disp_dev,
            font=('TkDefaultFont', 18), fg='blue').grid(row=1, column=1, padx=(5,20))

    POLL_MS = 200

    def poll_device():
        if status == 0:
            try:
                lib.CC_RequestPosition(serial_num)
                real_val = c_double()
                unit = lib.CC_GetPosition(serial_num)
                lib.CC_GetRealValueFromDeviceUnit(
                    serial_num, c_int(unit),
                    byref(real_val), 0
                )
                dev_var.set(real_val.value)
                homed = c_bool(False)
                lib.CC_GetHomingState(serial_num, byref(homed))
                print(homed_var.get())
                homed_var.set(homed.value)
            except Exception:
                pass
        root.after(POLL_MS, poll_device)

    root.after(POLL_MS, poll_device)

    # --- Section 2: Saved Positions ---
    sec2 = tk.LabelFrame(root, text="Saved Positions", padx=10, pady=10)
    sec2.pack(fill='x', padx=10, pady=5)

    for i, slot_var in enumerate(slots, start=1):
        tk.Label(sec2, text=f"Position {i}:")\
            .grid(row=i-1, column=0, sticky='w', padx=5, pady=2)
        tk.Entry(
            sec2, textvariable=slot_var, width=10,
            justify='center', state='readonly'
        ).grid(row=i-1, column=1, padx=5, pady=2)

        def make_set(idx):
            def do_set():
                slots[idx].set(current_pos.get())
                persist()
            return do_set

        def make_go(idx):
            def do_go():
                safe_set_current(slots[idx].get())
                update_position(current_pos.get())
                persist()
            return do_go

        SolidButton(sec2, text="Set", command=make_set(i-1))\
            .grid(row=i-1, column=2, padx=5, pady=2)
        SolidButton(sec2, text="Go",  command=make_go(i-1))\
            .grid(row=i-1, column=3, padx=5, pady=2)

    def reset_slots():
        for sv in slots:
            sv.set(0.0)
        persist()
    SolidButton(sec2, text="Reset All", command=reset_slots)\
        .grid(row=num_slots, column=0, columnspan=4,
              sticky='we', pady=(10, 0))

    # --- Section 3: Relative Move + Quick Moves ---
    sec3 = tk.LabelFrame(root, text="Relative Move", padx=10, pady=10)
    sec3.pack(fill='x', padx=10, pady=5)

    tk.Label(sec3, text="Forward Δ:")\
        .grid(row=0, column=0, sticky='e')
    fwd = DashedEntry(sec3)
    fwd.grid(row=0, column=1, padx=5)

    def do_forward():
        try:
            d = float(fwd.get())
            safe_set_current(current_pos.get() + d)
            update_position(current_pos.get())
            persist()
        except ValueError:
            pass

    SolidButton(sec3, text="Go", command=do_forward)\
        .grid(row=0, column=2, padx=5)

    quick_fwd = tk.Frame(sec3)
    quick_fwd.grid(row=1, column=0, columnspan=4, pady=(10, 20))
    for delta in [0.1, 1]:
        SolidButton(
            quick_fwd, text=f"+{delta}",
            width=3,
            command=lambda d=delta: (
                safe_set_current(current_pos.get()+d),
                update_position(current_pos.get()),
                persist()
            )
        ).pack(side='left', padx=4)

    tk.Label(sec3, text="Backward Δ:")\
        .grid(row=2, column=0, sticky='e')
    bwd = DashedEntry(sec3)
    bwd.grid(row=2, column=1, padx=5)

    def do_backward():
        try:
            d = float(bwd.get())
            safe_set_current(current_pos.get() - d)
            update_position(current_pos.get())
            persist()
        except ValueError:
            pass

    SolidButton(sec3, text="Go", command=do_backward)\
        .grid(row=2, column=2, padx=5)

    quick_bwd = tk.Frame(sec3)
    quick_bwd.grid(row=3, column=0, columnspan=4, pady=(10, 0))
    for delta in [0.1, 1]:
        SolidButton(
            quick_bwd, text=f"-{delta}",
            width=3,
            command=lambda d=delta: (
                safe_set_current(current_pos.get()-d),
                update_position(current_pos.get()),
                persist()
            )
        ).pack(side='left', padx=4)

    # --- Section 4: Manual Goto ---
    sec4 = tk.LabelFrame(root, text="Manual Goto", padx=10, pady=10)
    sec4.pack(fill='x', padx=10, pady=(5, 10))
    goto = DashedEntry(sec4)
    goto.pack(side='left', padx=5)

    def do_goto():
        try:
            v = float(goto.get())
            safe_set_current(v)
            update_position(current_pos.get())
            persist()
        except ValueError:
            pass

    SolidButton(sec4, text="Go", command=do_goto)\
        .pack(side='left', padx=5)

    def on_close():
        persist()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    build_gui()
