/** Run with BD_SOURCE_ROOT=/path/to/patched/BetterDiscord bun test this-file. */
import {test, expect, mock} from "bun:test";
import path from "node:path";

const root = process.env.BD_SOURCE_ROOT;
if (!root) throw new Error("BD_SOURCE_ROOT must point to the patched BetterDiscord checkout");
let bundle: any;
let actions: any;
let failDiscovery = false;
let interceptors = 0;
let warnings = 0;
let requires: any[] = [];
let factoryExports: any;
let menuComponent: any;
let opens = 0;
let closes = 0;
const lazyListeners = new Set<Function>();
const webpackRequire: any = (id: string) => {requires.push(id); if (id === "101" && factoryExports) return factoryExports; throw new Error("Unexpected factory require: " + id);};
webpackRequire.m = {};
mock.module(path.join(root, "src/betterdiscord/webpack/index.ts"), () => ({
    Filters: {byStrings: () => () => true}, lazyListeners, webpackRequire,
    getByKeys: () => {if (failDiscovery) throw new Error("Unsupported runtime"); return bundle;},
    getBySource: () => actions,
    getModule: () => menuComponent,
    getLazyByKeys: () => new Promise(() => {})
}));
mock.module(path.join(root, "src/common/logger.ts"), () => ({default: {
    warn: () => warnings++, stacktrace: () => {}, error: () => {}
}}));
mock.module(path.join(root, "src/betterdiscord/modules/discordmodules.ts"), () => ({default: {
    Dispatcher: {addInterceptor: () => interceptors++}
}}));
mock.module(path.join(root, "src/betterdiscord/modules/nodepatcher.ts"), () => ({default: class {patch() {}}}));
mock.module(path.join(root, "src/betterdiscord/modules/dommanager.ts"), () => ({default: {injectStyle() {}}}));
// React's element identity is enough here; preserve hook/component execution for
// upstream's own React tests rather than recreating its rendering implementation.
mock.module("react", () => ({default: {createElement: (type: any, props: any, ...children: any[]) => ({type, props, children}), isValidElement: () => false}}));

const source = path.join(root, "src/betterdiscord/api/contextmenu.ts");
const delay = () => new Promise(resolve => setTimeout(resolve, 10));
const components = () => Object.fromEntries(["MenuSeparator", "MenuCheckboxItem", "MenuRadioItem", "MenuControlItem", "MenuGroup", "MenuItem", "Menu"].map(k => [k, function NativeMenuComponent() {}]));

test("missing optional menu does not abort module import, and unsupported calls are safe", async () => {
    const {default: ContextMenu} = await import(source);
    const menu = new ContextMenu();
    expect(menu.buildItem({label: "example"})).toBeNull();
    expect(menu.buildMenuChildren([])).toEqual([]);
    expect(menu.buildMenu([])({})).toBeNull();
    expect(menu.open({}, () => null)).toBeUndefined();
    menu.close();
    expect(menu.Item).toBeUndefined();
    expect(requires).toEqual([]);
    expect(interceptors).toBe(0);
    expect(warnings).toBe(1);
    expect(lazyListeners.size).toBe(1);
});

test("discovery exceptions remain local to optional API", async () => {
    const {default: ContextMenu} = await import(source);
    failDiscovery = true;
    expect(() => new ContextMenu().buildItem({label: "example"})).not.toThrow();
    failDiscovery = false;
});

test("partial discovery does not publish components or register interceptors", async () => {
    const {default: ContextMenu} = await import(source);
    bundle = components();
    actions = {openContextMenu: () => opens++};
    expect(new ContextMenu().Item).toBeUndefined();
    expect(interceptors).toBe(0);
    expect(requires).toEqual([]);
});

test("later chunk recovers existing instances, native component identity and actions", async () => {
    const {default: ContextMenu} = await import(source);
    const menu = new ContextMenu();
    actions = {openContextMenu: () => opens++, closeContextMenu: () => closes++};
    for (const listener of lazyListeners) {listener(); listener();}
    expect(interceptors).toBe(0); // retry must wait until the current factory completes
    await delay();
    expect(lazyListeners.size).toBe(0);
    expect(interceptors).toBe(1);
    expect(menu.Item).toBe(bundle.MenuItem);
    expect(menu.Separator).toBe(bundle.MenuSeparator);
    expect(menu.buildItem({label: "example"}).type).toBe(bundle.MenuItem);
    expect(menu.buildMenu([])({}).type).toBe(bundle.Menu);
    menu.open({}, () => null); menu.close();
    expect(opens).toBe(1); expect(closes).toBe(1);
    expect(requires).toEqual([]);
});

test("repeated successful calls keep a single native interceptor", async () => {
    const {default: ContextMenu} = await import(source);
    const menu = new ContextMenu();
    menu.buildItem({label: "a"}); menu.buildItem({label: "b"});
    expect(interceptors).toBe(1);
    expect(warnings).toBe(1);
});


test("a factory signature without its semantic parser never executes the factory", async () => {
    bundle = undefined;
    webpackRequire.m = {"101": {toString: () => "function a(e){return null}".repeat(5)}};
    const before = requires.length;
    const {default: ContextMenu} = await import(source + "?missing-parser");
    expect(new ContextMenu().Item).toBeUndefined();
    expect(requires.length).toBe(before);
});

test("supported legacy parser loads only the matched factory and preserves native menu elements", async () => {
    bundle = undefined;
    const native = components();
    factoryExports = {s: native.MenuSeparator, r: native.MenuRadioItem, c: native.MenuCheckboxItem,
        k: native.MenuControlItem, g: native.MenuGroup, i: native.MenuItem};
    menuComponent = native.Menu;
    webpackRequire.m = {
        "101": {toString: () => "function a(e){return null}function b(e){return null}function c(e){return null}function d(e){return null}function f(e){return null}"},
        "202": {toString: () => 'r(101);"Menu API only allows Items and groups of Items as children";' +
            ['s:separator','r:radio','c:checkbox','k:control','i:item'].map(pair => {
                const [key, type] = pair.split(':'); return `if(e.type===n.${key})return a.push({type:"${type}",x:1});`;
            }).join('') + 'if(e.type===n.g){a.push({type:"groupstart",x:1})}'}
    };
    const before = requires.length;
    const {default: ContextMenu} = await import(source + "?legacy");
    const menu = new ContextMenu();
    expect(menu.Item).toBe(native.MenuItem);
    expect(menu.Group).toBe(native.MenuGroup);
    expect(menu.Menu).toBe(native.Menu);
    expect(requires.slice(before)).toEqual(["101"]);
    expect(menu.buildItem({type: "separator"}).type).toBe(native.MenuSeparator);
});
