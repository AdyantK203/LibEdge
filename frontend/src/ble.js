// Student phone <-> library gateway over Bluetooth LE (Web Bluetooth, Chrome on Android / Bluefy on iOS).
export const UUID = {
  svc: "6c1b0001-9a4e-4e0f-8d0a-5b1d2c3e4f50",
  req: "6c1b0002-9a4e-4e0f-8d0a-5b1d2c3e4f50",
  rec: "6c1b0003-9a4e-4e0f-8d0a-5b1d2c3e4f50",
};
export const bluetoothSupported = () => typeof navigator !== "undefined" &&
  !!navigator.bluetooth && (window.isSecureContext || location.hostname === "localhost");
const enc = new TextEncoder(), dec = new TextDecoder();

export class BluetoothLink {
  kind = "bluetooth";
  async connect(onDrop) {
    const dev = await navigator.bluetooth.requestDevice({ filters: [{ services: [UUID.svc] }] });
    this.device = dev;
    dev.addEventListener("gattserverdisconnected", () => onDrop?.());
    const svc = await (await dev.gatt.connect()).getPrimaryService(UUID.svc);
    this.req = await svc.getCharacteristic(UUID.req);
    this.rec = await svc.getCharacteristic(UUID.rec);
    this.name = dev.name || "LibEdge";
  }
  async ask(n) {
    await this.rec.startNotifications();
    return new Promise((resolve, reject) => {
      let timer;
      const cleanup = () => {
        clearTimeout(timer);
        this.rec.removeEventListener("characteristicvaluechanged", onValue);
      };
      const onValue = (event) => {
        cleanup();
        try { resolve(JSON.parse(dec.decode(event.target.value))); }
        catch { reject(new Error("The library beacon returned an unreadable response. Please retry.")); }
      };
      timer = setTimeout(() => {
        cleanup();
        reject(new Error("The library beacon did not answer. Move closer and retry."));
      }, 7000);
      this.rec.addEventListener("characteristicvaluechanged", onValue);
      this.req.writeValue(enc.encode(JSON.stringify({ g: n }))).catch((error) => {
        cleanup();
        reject(error);
      });
    });
  }
}

// Desktop testing only: same payload, fetched from the backend over HTTP.
export class DemoLink {
  kind = "demo";
  async connect() { this.name = "Demo link"; }
  async ask(n) { return (await fetch(`/api/recommend?group=${n}`)).json(); }
}
