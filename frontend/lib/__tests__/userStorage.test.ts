import { beforeEach, describe, expect, it } from "vitest";

import { currentUserId, getUserItem, removeUserItem, setUserItem, userStorageKey } from "../userStorage";

describe("userStorage", () => {
  beforeEach(() => window.localStorage.clear());

  it("particiona una misma preferencia por cuenta", () => {
    setUserItem("moldesign_theme", "dark", "alice");
    setUserItem("moldesign_theme", "light", "bob");

    expect(getUserItem("moldesign_theme", "alice")).toBe("dark");
    expect(getUserItem("moldesign_theme", "bob")).toBe("light");
    removeUserItem("moldesign_theme", "alice");
    expect(getUserItem("moldesign_theme", "alice")).toBeNull();
    expect(getUserItem("moldesign_theme", "bob")).toBe("light");
  });

  it("no crea almacenamiento anónimo", () => {
    expect(userStorageKey("moldesign_theme", null)).toBeNull();
    expect(setUserItem("moldesign_theme", "dark", null)).toBe(false);
  });

  it("obtiene la identidad exclusivamente de la sesión autenticada", () => {
    window.localStorage.setItem("moldesign_auth", JSON.stringify({
      token: "token",
      user: { user_id: "alice", username: "Alice" },
    }));
    expect(currentUserId()).toBe("alice");
    expect(userStorageKey("preference")).toBe("preference:user:alice");
  });

  it("una sesión corrupta no cae en una clave global compartida", () => {
    window.localStorage.setItem("moldesign_auth", "{json roto");
    expect(currentUserId()).toBeNull();
    expect(setUserItem("private-draft", "secret")).toBe(false);
    expect(window.localStorage.getItem("private-draft")).toBeNull();
  });

  it("rechaza user_id vacío aunque exista un token", () => {
    window.localStorage.setItem("moldesign_auth", JSON.stringify({
      token: "token",
      user: { user_id: "   " },
    }));
    expect(currentUserId()).toBeNull();
  });
});
