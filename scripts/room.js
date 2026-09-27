/* Private room transport. The host key stays on this browser, never in invites. */
(() => {
  class RoomClient {
    constructor(onState, onConnection) {
      this.onState = onState;
      this.onConnection = onConnection;
      this.id = null;
      this.hostKey = null;
      this.revision = -1;
      this.connected = false;
      this.timer = null;
      this.stopped = false;
      this.busy = false;
    }
    async request(path, body, host = false) {
      const controller = new AbortController();
      // Free sync services may need a minute to wake up for the first room.
      const timeout = setTimeout(() => controller.abort(), path === '' ? 90000 : 10000);
      try {
        const base = window.CLUEGRID_API_URL ? `${window.CLUEGRID_API_URL.replace(/\/$/, '')}/` : document.baseURI;
        const response = await fetch(new URL(`api/rooms${path}`, base), {
          method: 'POST', cache: 'no-store', signal: controller.signal,
          headers: { 'Content-Type': 'application/json', ...(host ? { Authorization: `Bearer ${this.hostKey}` } : {}) },
          body: JSON.stringify(body),
        });
        const isJSON = response.headers.get('content-type')?.includes('application/json');
        const result = isJSON ? await response.json() : {};
        if (!response.ok || !isJSON) {
          const error = new Error(result.error || 'The room service is unavailable. Please try again later.');
          error.status = response.status;
          error.state = result.state;
          throw error;
        }
        return result;
      } finally { clearTimeout(timeout); }
    }
    setConnection(connected, message = '') {
      const changed = this.connected !== connected;
      this.connected = connected;
      if (changed || message) this.onConnection(connected, message);
    }
    apply(state) {
      if (this.stopped) return;
      if (state.revision <= this.revision) return;
      const first = this.revision < 0;
      this.revision = state.revision;
      this.onState(state, first);
    }
    async create(game) {
      const result = await this.request('', { game });
      this.id = result.room;
      this.hostKey = result.hostKey;
      try { localStorage.setItem(`cluegrid:host:${this.id}`, this.hostKey); }
      catch { /* The current tab retains hosting if browser storage is blocked. */ }
      this.setConnection(true);
      this.apply(result.state);
      this.schedule();
      return result.state;
    }
    async join(id) {
      this.id = id;
      try { this.hostKey = localStorage.getItem(`cluegrid:host:${id}`); }
      catch { /* A browser without the host key joins as a guest. */ }
      await this.poll();
    }
    schedule() {
      clearTimeout(this.timer);
      if (!this.stopped) this.timer = setTimeout(() => this.poll(), this.connected ? 1000 : 3000);
    }
    stop() {
      this.stopped = true;
      clearTimeout(this.timer);
    }
    async poll() {
      try {
        const result = await this.request('/state', { room: this.id });
        if (this.stopped) return;
        this.setConnection(true);
        this.apply(result.state);
      } catch (error) {
        if (this.stopped) return;
        this.setConnection(false, 'Sync unavailable. Continue playing locally.');
      } finally { this.schedule(); }
    }
    async act(action, details = {}) {
      if (!this.hostKey || !this.connected || this.busy || this.stopped) return false;
      this.busy = true;
      this.onConnection(this.connected, 'Saving move…');
      try {
        const result = await this.request('/action', { ...details, room: this.id, revision: this.revision, action }, true);
        if (this.stopped) return false;
        this.apply(result.state);
      } catch (error) {
        if (this.stopped) return false;
        if (error.status === 409 && error.state) {
          this.apply(error.state);
          return true;
        }
        if (error.state) this.apply(error.state);
        if (error.status === 403) {
          this.hostKey = null;
          try { localStorage.removeItem(`cluegrid:host:${this.id}`); } catch { /* Optional storage. */ }
        }
        this.setConnection(false, 'Sync unavailable. Continue playing locally.');
        return false;
      } finally {
        this.busy = false;
        if (!this.stopped) this.onConnection(this.connected);
      }
      this.setConnection(true);
      return true;
    }
  }
  window.RoomClient = RoomClient;
})();
