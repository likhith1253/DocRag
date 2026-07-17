#!/usr/bin/env python3
"""
Benchmark Builder v2 — Constructs the full benchmark for Textual with
VERIFIED evidence lines derived from AST parsing.

Ground truth = file path + exact AST-derived line range.
Chunk IDs are SECONDARY metadata only.
All entity names verified against actual repository source.
"""

import ast
import os
import json
import hashlib
import random
from dataclasses import dataclass, asdict, field
from typing import List, Optional

REPO_ROOT = "d:/Document_RAG/eval/external_benchmark/repos/textual"
SRC_ROOT = os.path.join(REPO_ROOT, "src", "textual")
OUTPUT_PATH = "d:/Document_RAG/eval/external_benchmark/full_benchmark.json"

random.seed(42)


@dataclass
class BenchmarkEntry:
    id: str
    question: str
    evidence_file: str
    evidence_lines: str
    ground_truth_chunks: List[str]
    reasoning_capability: str
    retrieval_complexity: str
    difficulty: str
    verification_metadata: dict
    secondary_evidence_file: Optional[str] = None
    secondary_evidence_lines: Optional[str] = None


def sha_id(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def rel(abs_path: str) -> str:
    return os.path.relpath(abs_path, REPO_ROOT).replace("\\", "/")


def get_file_line_count(path: str) -> int:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return len(f.readlines())


def parse_entities(abs_path: str):
    """Return dict keyed by qualified name -> (start, end) for all class-level and top-level defs.
    Also recurses into nested classes (e.g., Button.Pressed).
    """
    with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
        src = f.read()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return {}
    entities = {}
    # Top-level classes and functions
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            entities[node.name] = (node.lineno, node.end_lineno)
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    entities[f"{node.name}.{item.name}"] = (item.lineno, item.end_lineno)
                elif isinstance(item, ast.ClassDef):
                    # Nested class (e.g., Button.Pressed)
                    entities[item.name] = (item.lineno, item.end_lineno)
                    entities[f"{node.name}.{item.name}"] = (item.lineno, item.end_lineno)
                    for sub in item.body:
                        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            entities[f"{node.name}.{item.name}.{sub.name}"] = (sub.lineno, sub.end_lineno)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            entities[node.name] = (node.lineno, node.end_lineno)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    entities[t.id] = (node.lineno, node.end_lineno)
    return entities


def make_chunk_id(evidence_file, start, end):
    return sha_id(f"{evidence_file}:{start}:{end}")


def build_entries() -> List[BenchmarkEntry]:
    entries = []

    # Paths
    app_path         = os.path.join(SRC_ROOT, "app.py")
    widget_path      = os.path.join(SRC_ROOT, "widget.py")
    button_path      = os.path.join(SRC_ROOT, "widgets", "_button.py")
    message_path     = os.path.join(SRC_ROOT, "message.py")
    screen_path      = os.path.join(SRC_ROOT, "screen.py")
    reactive_path    = os.path.join(SRC_ROOT, "reactive.py")
    dom_path         = os.path.join(SRC_ROOT, "dom.py")
    events_path      = os.path.join(SRC_ROOT, "events.py")
    message_pump_path = os.path.join(SRC_ROOT, "message_pump.py")
    driver_path      = os.path.join(SRC_ROOT, "driver.py")
    binding_path     = os.path.join(SRC_ROOT, "binding.py")
    color_path       = os.path.join(SRC_ROOT, "color.py")
    timer_path       = os.path.join(SRC_ROOT, "timer.py")
    worker_path      = os.path.join(SRC_ROOT, "worker.py")
    signal_path      = os.path.join(SRC_ROOT, "signal.py")
    const_path       = os.path.join(SRC_ROOT, "constants.py")
    feat_path        = os.path.join(SRC_ROOT, "features.py")
    dispatch_path    = os.path.join(SRC_ROOT, "_dispatch_key.py")
    pilot_path       = os.path.join(SRC_ROOT, "pilot.py")
    work_dec_path    = os.path.join(SRC_ROOT, "_work_decorator.py")
    compositor_path  = os.path.join(SRC_ROOT, "_compositor.py")
    walk_path        = os.path.join(SRC_ROOT, "walk.py")

    # Parse entities from each file
    app_e    = parse_entities(app_path)
    wid_e    = parse_entities(widget_path)
    btn_e    = parse_entities(button_path)
    msg_e    = parse_entities(message_path)
    scr_e    = parse_entities(screen_path)
    rea_e    = parse_entities(reactive_path)
    dom_e    = parse_entities(dom_path)
    ev_e     = parse_entities(events_path)
    pump_e   = parse_entities(message_pump_path)
    drv_e    = parse_entities(driver_path)
    bind_e   = parse_entities(binding_path)
    clr_e    = parse_entities(color_path)
    tmr_e    = parse_entities(timer_path)
    wrk_e    = parse_entities(worker_path)
    sig_e    = parse_entities(signal_path)
    disp_e   = parse_entities(dispatch_path)
    pilot_e  = parse_entities(pilot_path)
    work_dec_e = parse_entities(work_dec_path)
    comp_e   = parse_entities(compositor_path)
    walk_e   = parse_entities(walk_path)

    def add(id_, question, path, entity_key, ents, cap, comp, diff, notes,
            sec_path=None, sec_entity=None, sec_ents=None):
        if entity_key not in ents:
            print(f"  [SKIP] {id_}: entity '{entity_key}' not found in {rel(path)}")
            return
        s, e = ents[entity_key]
        ev_lines = f"{s}-{e}"
        cid = make_chunk_id(rel(path), s, e)
        chunks = [cid]
        sec_file = sec_lines = None
        if sec_path and sec_entity and sec_ents:
            if sec_entity in sec_ents:
                ss, se = sec_ents[sec_entity]
                sec_file = rel(sec_path)
                sec_lines = f"{ss}-{se}"
                chunks.append(make_chunk_id(sec_file, ss, se))
            else:
                print(f"  [WARN] {id_}: secondary entity '{sec_entity}' not found in {rel(sec_path)}")
        entries.append(BenchmarkEntry(
            id=id_,
            question=question,
            evidence_file=rel(path),
            evidence_lines=ev_lines,
            ground_truth_chunks=chunks,
            reasoning_capability=cap,
            retrieval_complexity=comp,
            difficulty=diff,
            verification_metadata={
                "verified": True,
                "verifier": "AST_Parser_v2",
                "notes": notes
            },
            secondary_evidence_file=sec_file,
            secondary_evidence_lines=sec_lines
        ))

    def add_file(id_, question, path, cap, comp, diff, notes):
        """Add a whole-file entry (for module-level questions)."""
        total = get_file_line_count(path)
        ev_file = rel(path)
        cid = make_chunk_id(ev_file, 1, total)
        entries.append(BenchmarkEntry(
            id=id_,
            question=question,
            evidence_file=ev_file,
            evidence_lines=f"1-{total}",
            ground_truth_chunks=[cid],
            reasoning_capability=cap,
            retrieval_complexity=comp,
            difficulty=diff,
            verification_metadata={
                "verified": True,
                "verifier": "AST_Parser_v2",
                "notes": notes
            }
        ))

    # ── Control-flow reasoning (20) ──────────────────────────────────────────
    add("textual_cf_01",
        "How does `App.run()` initialize the asyncio event loop and which driver startup sequence does it follow?",
        app_path, "App.run", app_e,
        "control-flow reasoning", "multi-hop", "hard",
        "App.run is the synchronous entry point calling run_async. Multi-hop: requires reading App.run_async and App._build_driver.",
        sec_path=app_path, sec_entity="App.run_async", sec_ents=app_e)

    add("textual_cf_02",
        "What is the async execution flow inside `App.run_async()` before the event loop begins processing messages?",
        app_path, "App.run_async", app_e,
        "control-flow reasoning", "multi-hop", "hard",
        "App.run_async orchestrates driver startup and screen push before the event loop. Multi-hop: intersects driver.py.",
        sec_path=driver_path, sec_entity="Driver", sec_ents=drv_e)

    add("textual_cf_03",
        "How does `MessagePump._dispatch_message()` resolve the correct handler method to call for a given message?",
        message_pump_path, "MessagePump._dispatch_message", pump_e,
        "control-flow reasoning", "single-hop", "medium",
        "Single-hop: dispatch logic is self-contained in message_pump.py.")

    add("textual_cf_04",
        "How does `MessagePump._process_messages_loop()` process the message queue and handle backpressure?",
        message_pump_path, "MessagePump._process_messages_loop", pump_e,
        "control-flow reasoning", "single-hop", "hard",
        "Single-hop: the full message processing loop is in message_pump.py.")

    add("textual_cf_05",
        "Trace the sequence of calls that occurs when `Widget.remove()` is invoked on a mounted widget.",
        widget_path, "Widget.remove", wid_e,
        "control-flow reasoning", "multi-hop", "hard",
        "Multi-hop: Widget.remove posts a message that crosses widget.py and message_pump.py.")

    add("textual_cf_06",
        "What is the complete call chain inside `Widget.mount()` from invocation to DOM attachment?",
        widget_path, "Widget.mount", wid_e,
        "control-flow reasoning", "multi-hop", "hard",
        "Multi-hop: Widget.mount calls _find_mount_point and interacts with DOM and message bus.",
        sec_path=widget_path, sec_entity="Widget._find_mount_point", sec_ents=wid_e)

    add("textual_cf_07",
        "How does `App.push_screen()` manage the screen stack and trigger screen lifecycle callbacks?",
        app_path, "App.push_screen", app_e,
        "control-flow reasoning", "multi-hop", "hard",
        "Multi-hop: push_screen interacts with screen.py lifecycle methods and _replace_screen.")

    add("textual_cf_08",
        "What is the control flow of `App.pop_screen()` including focus restoration and outgoing screen teardown?",
        app_path, "App.pop_screen", app_e,
        "control-flow reasoning", "multi-hop", "hard",
        "Multi-hop: pop_screen triggers screen._on_mount and focus events crossing screen.py.")

    add("textual_cf_09",
        "How does `Button._on_click()` produce a `Button.Pressed` message on the message bus?",
        button_path, "Button._on_click", btn_e,
        "control-flow reasoning", "multi-hop", "medium",
        "Multi-hop: _on_click calls self.press() which posts Pressed. Cross-file via message_pump.",
        sec_path=button_path, sec_entity="Button.press", sec_ents=btn_e)

    add("textual_cf_10",
        "What is the execution order between `Widget._on_mount()` and any user-defined `Widget.on_mount()` override?",
        widget_path, "Widget._on_mount", wid_e,
        "control-flow reasoning", "single-hop", "medium",
        "Single-hop: _on_mount and its relationship to on_mount is in widget.py.")

    add("textual_cf_11",
        "How does `Driver.start_application_mode()` signal the application to begin rendering?",
        driver_path, "Driver.start_application_mode", drv_e,
        "control-flow reasoning", "single-hop", "medium",
        "Single-hop: start_application_mode is defined in driver.py.")

    add("textual_cf_12",
        "How does `Screen.set_focus()` propagate focus change events to the DOM and trigger blur/focus lifecycle events?",
        screen_path, "Screen.set_focus", scr_e,
        "control-flow reasoning", "multi-hop", "hard",
        "Multi-hop: set_focus posts events that flow through dom.py and message_pump.py.")

    add("textual_cf_13",
        "What is the teardown sequence when `App.exit()` is called, including driver cleanup?",
        app_path, "App.exit", app_e,
        "control-flow reasoning", "multi-hop", "hard",
        "Multi-hop: App.exit coordinates with driver.py teardown and screen lifecycle.")

    add("textual_cf_14",
        "How does `Timer._run()` manage interval callbacks and handle cancellation mid-interval?",
        timer_path, "Timer._run", tmr_e,
        "control-flow reasoning", "single-hop", "medium",
        "Single-hop: Timer._run is self-contained in timer.py.")

    add("textual_cf_15",
        "How does `dispatch_key()` determine which widget receives a keypress and what happens if no handler is found?",
        dispatch_path, "dispatch_key", disp_e,
        "control-flow reasoning", "single-hop", "medium",
        "Single-hop: key dispatch logic is fully in _dispatch_key.py.")

    add("textual_cf_16",
        "How does `Widget.scroll_to()` calculate the scroll delta and initiate the animation sequence?",
        widget_path, "Widget.scroll_to", wid_e,
        "control-flow reasoning", "multi-hop", "hard",
        "Multi-hop: scroll_to delegates to _animator.py for animation.")

    add("textual_cf_17",
        "How does `App.action_focus_next()` cycle focus across all focusable widgets in the DOM?",
        app_path, "App.action_focus_next", app_e,
        "control-flow reasoning", "multi-hop", "medium",
        "Multi-hop: action_focus_next uses DOM traversal via screen.py.")

    add("textual_cf_18",
        "What happens when `MessagePump.post_message()` is called before the pump has started processing?",
        message_pump_path, "MessagePump.post_message", pump_e,
        "control-flow reasoning", "single-hop", "medium",
        "Single-hop: queue behavior during pre-run state is documented in message_pump.py.")

    add("textual_cf_19",
        "How does `App.install_screen()` register a named screen for deferred use?",
        app_path, "App.install_screen", app_e,
        "control-flow reasoning", "single-hop", "easy",
        "Single-hop: install_screen is in app.py and does not cross file boundaries.")

    add("textual_cf_20",
        "How does `Widget._on_unmount()` clean up reactive watchers before the widget is detached from the DOM?",
        widget_path, "Widget._on_unmount", wid_e,
        "control-flow reasoning", "single-hop", "medium",
        "Single-hop: _on_unmount cleanup is in widget.py.")

    # ── Data-flow reasoning (16) ─────────────────────────────────────────────
    add("textual_df_01",
        "How does a `reactive` attribute value change propagate to its corresponding `watch_*` method in `Widget`?",
        reactive_path, "Reactive.__set__", rea_e,
        "data-flow reasoning", "multi-hop", "hard",
        "Multi-hop: __set__ triggers watcher dispatch via message_pump.py.")

    add("textual_df_02",
        "What data does the `Message` base class carry when posted from a child widget to a parent?",
        message_path, "Message", msg_e,
        "data-flow reasoning", "single-hop", "medium",
        "Single-hop: Message class structure is in message.py.")

    add("textual_df_03",
        "How does the `Button.Pressed` message carry a reference to the originating `Button` widget instance?",
        button_path, "Button.Pressed", btn_e,
        "data-flow reasoning", "single-hop", "easy",
        "Single-hop: Button.Pressed is defined as a nested class in _button.py with a button attribute.")

    add("textual_df_04",
        "How does message routing work such that a `Button.Pressed` reaches a parent `Screen` handler?",
        message_pump_path, "MessagePump._dispatch_message", pump_e,
        "data-flow reasoning", "multi-hop", "hard",
        "Multi-hop: message routing from button to screen crosses widget.py and message_pump.py.",
        sec_path=button_path, sec_entity="Button.press", sec_ents=btn_e)

    add("textual_df_05",
        "Describe the data flow from a raw terminal keypress to a `Key` event object inside the application.",
        events_path, "Key", ev_e,
        "data-flow reasoning", "multi-hop", "hard",
        "Multi-hop: keypress data flows from _xterm_parser.py through driver to events.Key.")

    add("textual_df_06",
        "How does `Color.blend()` combine two color values — what numeric operations does it perform?",
        color_path, "Color.blend", clr_e,
        "data-flow reasoning", "single-hop", "medium",
        "Single-hop: Color.blend is self-contained in color.py.")

    add("textual_df_07",
        "How does `DOMNode.query()` pass CSS selector criteria through the DOM tree to collect matching nodes?",
        dom_path, "DOMNode.query", dom_e,
        "data-flow reasoning", "multi-hop", "hard",
        "Multi-hop: query uses CSS selector engine in css/ module.")

    add("textual_df_08",
        "What data transformation occurs between `Widget.render()` output and the final terminal Strip object?",
        widget_path, "Widget.render", wid_e,
        "data-flow reasoning", "multi-hop", "hard",
        "Multi-hop: render output flows through strip.py and _compositor.py.")

    add("textual_df_09",
        "How does `Reactive.__get__` return the attribute value — from a backing store or computed on access?",
        reactive_path, "Reactive.__get__", rea_e,
        "data-flow reasoning", "single-hop", "medium",
        "Single-hop: Reactive.__get__ is self-contained in reactive.py.")

    add("textual_df_10",
        "How does a `Worker` pass its result back to the owning `App` context after async completion?",
        worker_path, "Worker._run_async", wrk_e,
        "data-flow reasoning", "multi-hop", "hard",
        "Multi-hop: Worker result flows through WorkerManager back to App context.")

    add("textual_df_11",
        "How does `App.notify()` construct a notification and dispatch it to the active screen?",
        app_path, "App.notify", app_e,
        "data-flow reasoning", "single-hop", "easy",
        "Single-hop: App.notify is fully in app.py.")

    add("textual_df_12",
        "How does `Signal.publish()` deliver a value to all registered subscribers?",
        signal_path, "Signal.publish", sig_e,
        "data-flow reasoning", "single-hop", "medium",
        "Single-hop: Signal.publish is in signal.py.")

    add("textual_df_13",
        "How does `DOMNode.set_styles()` apply an inline style string to the DOM node's style object?",
        dom_path, "DOMNode.set_styles", dom_e,
        "data-flow reasoning", "single-hop", "medium",
        "Single-hop: set_styles is in dom.py.")

    add("textual_df_14",
        "What is the data pipeline inside `Widget.get_content_width()` for computing a widget's intrinsic content width?",
        widget_path, "Widget.get_content_width", wid_e,
        "data-flow reasoning", "single-hop", "medium",
        "Single-hop: get_content_width is in widget.py.")

    add("textual_df_15",
        "How does `MessagePump._dispatch_message()` handle exceptions raised inside a message handler?",
        message_pump_path, "MessagePump._dispatch_message", pump_e,
        "data-flow reasoning", "single-hop", "medium",
        "Single-hop: exception handling is in _dispatch_message in message_pump.py.")

    add("textual_df_16",
        "How does `App._replace_screen()` swap the current screen and transfer any pending messages?",
        app_path, "App._replace_screen", app_e,
        "data-flow reasoning", "multi-hop", "hard",
        "Multi-hop: _replace_screen interacts with screen.py lifecycle and message queues.")

    # ── Architectural reasoning (24) ─────────────────────────────────────────
    add("textual_ar_01",
        "What is the class hierarchy of `Widget` and which base classes does it inherit from?",
        widget_path, "Widget", wid_e,
        "architectural reasoning", "single-hop", "easy",
        "Single-hop: Widget class definition with MRO bases is in widget.py.")

    add("textual_ar_02",
        "How is `App` structured relative to `MessagePump` and `DOMNode` — what does each parent provide?",
        app_path, "App", app_e,
        "architectural reasoning", "multi-hop", "hard",
        "Multi-hop: requires reading App, MessagePump, and DOMNode class definitions across files.",
        sec_path=message_pump_path, sec_entity="MessagePump", sec_ents=pump_e)

    add("textual_ar_03",
        "What is the purpose of `DOMNode` and how does it form a shared base for both `App` and `Widget`?",
        dom_path, "DOMNode", dom_e,
        "architectural reasoning", "multi-hop", "hard",
        "Multi-hop: DOMNode is a shared base — comparing dom.py, app.py, widget.py is required.")

    add("textual_ar_04",
        "How does the `Screen` class act as both a `Widget` and a layout container for its children?",
        screen_path, "Screen", scr_e,
        "architectural reasoning", "single-hop", "medium",
        "Single-hop: Screen class definition and responsibility are in screen.py.")

    add("textual_ar_05",
        "What is the role of `MessagePump` in the Textual architecture and what interface does it expose to subclasses?",
        message_pump_path, "MessagePump", pump_e,
        "architectural reasoning", "single-hop", "medium",
        "Single-hop: MessagePump class is self-contained in message_pump.py.")

    add("textual_ar_06",
        "How does `Binding` define a keyboard shortcut and link it to an action string?",
        binding_path, "Binding", bind_e,
        "architectural reasoning", "single-hop", "easy",
        "Single-hop: Binding dataclass is in binding.py.")

    add("textual_ar_07",
        "What is the abstract interface of `Driver` and which methods must every concrete driver implement?",
        driver_path, "Driver", drv_e,
        "architectural reasoning", "single-hop", "medium",
        "Single-hop: Driver abstract interface is in driver.py.")

    add("textual_ar_08",
        "How does the `Reactive` descriptor integrate with `Widget` and `DOMNode`'s attribute system?",
        reactive_path, "Reactive", rea_e,
        "architectural reasoning", "multi-hop", "hard",
        "Multi-hop: Reactive descriptor requires reactive.py and widget.py to understand fully.",
        sec_path=widget_path, sec_entity="Widget", sec_ents=wid_e)

    add("textual_ar_09",
        "What is the role of the `Worker` class and how does it run background tasks within the Textual event loop?",
        worker_path, "Worker", wrk_e,
        "architectural reasoning", "single-hop", "medium",
        "Single-hop: Worker class is in worker.py.")

    add("textual_ar_10",
        "How does `App.compose()` establish the initial widget tree before mounting begins?",
        app_path, "App.compose", app_e,
        "architectural reasoning", "single-hop", "easy",
        "Single-hop: App.compose is in app.py.")

    add("textual_ar_11",
        "How does Textual separate rendering responsibilities between `Widget.render()` and `_compositor.py`?",
        widget_path, "Widget.render", wid_e,
        "architectural reasoning", "multi-hop", "hard",
        "Multi-hop: rendering pipeline spans widget.py and _compositor.py.",
        sec_path=compositor_path, sec_entity="Compositor", sec_ents=comp_e)

    add("textual_ar_12",
        "What responsibilities does `BindingsMap` have in Textual's key-binding resolution system?",
        binding_path, "BindingsMap", bind_e,
        "architectural reasoning", "single-hop", "medium",
        "Single-hop: BindingsMap is in binding.py.")

    add("textual_ar_13",
        "How does `Screen.focus_next()` interact with the DOM to select the next focusable widget?",
        screen_path, "Screen.focus_next", scr_e,
        "architectural reasoning", "multi-hop", "medium",
        "Multi-hop: focus_next iterates DOM nodes using _widget_navigation.py utilities.")

    add("textual_ar_14",
        "What does the `ComposeResult` type alias represent and how does Textual consume its generator output?",
        app_path, "ComposeResult", app_e,
        "architectural reasoning", "single-hop", "easy",
        "Single-hop: ComposeResult type alias is defined at module level in app.py.")

    add("textual_ar_15",
        "How does `DOMNode.ancestors` traverse the DOM tree upward to the root?",
        dom_path, "DOMNode.ancestors", dom_e,
        "architectural reasoning", "single-hop", "easy",
        "Single-hop: ancestors property is in dom.py.")

    add("textual_ar_16",
        "How does Textual merge `App.DEFAULT_CSS` with widget-level `DEFAULT_CSS` during style resolution?",
        app_path, "App", app_e,
        "architectural reasoning", "multi-hop", "hard",
        "Multi-hop: DEFAULT_CSS merging requires app.py and the CSS cascade rules in css/.")

    add("textual_ar_17",
        "How does `Timer` integrate with the asyncio event loop managed by `MessagePump`?",
        timer_path, "Timer", tmr_e,
        "architectural reasoning", "multi-hop", "medium",
        "Multi-hop: Timer uses asyncio from message_pump.py context.",
        sec_path=message_pump_path, sec_entity="MessagePump.set_timer", sec_ents=pump_e)

    add("textual_ar_18",
        "What is the `Pilot` class and how does it enable headless testing of Textual applications?",
        pilot_path, "Pilot", pilot_e,
        "architectural reasoning", "single-hop", "medium",
        "Single-hop: Pilot class is in pilot.py.")

    add("textual_ar_19",
        "How does `App.set_focus()` delegate to `Screen.set_focus()` and what is the separation of concerns?",
        app_path, "App.set_focus", app_e,
        "architectural reasoning", "multi-hop", "medium",
        "Multi-hop: App.set_focus delegates to screen.py for actual focus change.",
        sec_path=screen_path, sec_entity="Screen.set_focus", sec_ents=scr_e)

    add("textual_ar_20",
        "What architectural pattern does Textual use for widget lookup via `DOMNode.query_one()`?",
        dom_path, "DOMNode.query_one", dom_e,
        "architectural reasoning", "multi-hop", "hard",
        "Multi-hop: query_one uses CSS selector engine in css/ subdirectory.")

    add("textual_ar_21",
        "How does `App.get_screen()` locate and return an installed screen by name?",
        app_path, "App.get_screen", app_e,
        "architectural reasoning", "single-hop", "easy",
        "Single-hop: get_screen is in app.py.")

    add("textual_ar_22",
        "How does `App._build_driver()` select the appropriate driver class based on environment conditions?",
        app_path, "App._build_driver", app_e,
        "architectural reasoning", "multi-hop", "hard",
        "Multi-hop: driver selection in App references drivers/ subdirectory classes.")

    add("textual_ar_23",
        "How does `Widget.focus()` propagate a focus request upward to the active Screen?",
        widget_path, "Widget.focus", wid_e,
        "architectural reasoning", "multi-hop", "medium",
        "Multi-hop: focus propagation: widget.py -> screen.py.",
        sec_path=screen_path, sec_entity="Screen.set_focus", sec_ents=scr_e)

    add("textual_ar_24",
        "How does `walk_depth_first()` in `walk.py` traverse the widget tree and what order does it visit nodes?",
        walk_path, "walk_depth_first", walk_e,
        "architectural reasoning", "single-hop", "medium",
        "Single-hop: walk_depth_first is self-contained in walk.py.")

    # ── API reasoning (12) ───────────────────────────────────────────────────
    add("textual_api_01",
        "What is the full signature of `App.run()` and what parameters can a developer pass to customize startup?",
        app_path, "App.run", app_e,
        "API reasoning", "single-hop", "easy",
        "Single-hop: App.run signature is in app.py.")

    add("textual_api_02",
        "What does `Widget.mount()` return and how can a caller await completion of the mounting operation?",
        widget_path, "Widget.mount", wid_e,
        "API reasoning", "single-hop", "easy",
        "Single-hop: Widget.mount return type is in widget.py.")

    add("textual_api_03",
        "What arguments does `App.push_screen()` accept and what type does it return?",
        app_path, "App.push_screen", app_e,
        "API reasoning", "single-hop", "easy",
        "Single-hop: App.push_screen signature is in app.py.")

    add("textual_api_04",
        "How is `DOMNode.query()` called and what CSS selector syntax does it support?",
        dom_path, "DOMNode.query", dom_e,
        "API reasoning", "single-hop", "medium",
        "Single-hop: query method signature is in dom.py.")

    add("textual_api_05",
        "What is the public API of `_work_decorator.work` for creating background workers?",
        work_dec_path, "work", work_dec_e,
        "API reasoning", "single-hop", "medium",
        "Single-hop: the @work decorator definition is in _work_decorator.py.")

    add("textual_api_06",
        "How does a developer register a `Binding` and what format must the action string follow?",
        binding_path, "Binding", bind_e,
        "API reasoning", "single-hop", "easy",
        "Single-hop: Binding constructor and fields are in binding.py.")

    add("textual_api_07",
        "What is the public API of `Pilot` for simulating user input in headless tests?",
        pilot_path, "Pilot", pilot_e,
        "API reasoning", "single-hop", "medium",
        "Single-hop: Pilot API is in pilot.py.")

    add("textual_api_08",
        "What does `MessagePump.call_after_refresh()` do and when should it be used over `call_later()`?",
        message_pump_path, "MessagePump.call_after_refresh", pump_e,
        "API reasoning", "single-hop", "medium",
        "Single-hop: call_after_refresh is in message_pump.py.")

    add("textual_api_09",
        "How does `MessagePump.set_timer()` work and what does it return to the caller?",
        message_pump_path, "MessagePump.set_timer", pump_e,
        "API reasoning", "single-hop", "easy",
        "Single-hop: set_timer is in message_pump.py.")

    add("textual_api_10",
        "What is the return type and error behavior of `DOMNode.query_one()` when no match is found?",
        dom_path, "DOMNode.query_one", dom_e,
        "API reasoning", "single-hop", "medium",
        "Single-hop: query_one is in dom.py.")

    add("textual_api_11",
        "How does `DOMNode.add_class()` modify the widget's CSS class list and trigger CSS re-evaluation?",
        dom_path, "DOMNode.add_class", dom_e,
        "API reasoning", "single-hop", "easy",
        "Single-hop: add_class is in dom.py.")

    add("textual_api_12",
        "What does `App.copy_to_clipboard()` do and under what conditions can it fail silently?",
        app_path, "App.copy_to_clipboard", app_e,
        "API reasoning", "single-hop", "medium",
        "Single-hop: copy_to_clipboard is in app.py.")

    # ── Configuration reasoning (8) ──────────────────────────────────────────
    add("textual_cfg_01",
        "What CSS pseudo-classes are available to Textual widgets and where are they mapped to Python conditions?",
        widget_path, "Widget", wid_e,
        "configuration reasoning", "single-hop", "medium",
        "Single-hop: PSEUDO_CLASSES dict is inside the Widget class body in widget.py.")

    add("textual_cfg_02",
        "How is `DEFAULT_CSS` in a widget parsed and integrated with user-provided application CSS?",
        widget_path, "Widget", wid_e,
        "configuration reasoning", "multi-hop", "hard",
        "Multi-hop: DEFAULT_CSS is processed by the CSS cascade logic in css/.")

    add("textual_cfg_03",
        "How does `App.CSS` interact with widget-level `DEFAULT_CSS` during stylesheet resolution?",
        app_path, "App", app_e,
        "configuration reasoning", "multi-hop", "hard",
        "Multi-hop: CSS resolution requires understanding app.py and css/ cascade rules.")

    add_file("textual_cfg_04",
        "What environment variables and module-level constants control Textual's debug and logging behavior?",
        const_path, "configuration reasoning", "single-hop", "easy",
        "Single-hop: all configuration constants are in constants.py.")

    add("textual_cfg_05",
        "How does the `Button`'s `variant` parameter translate to CSS modifier classes on the rendered button?",
        button_path, "Button.__init__", btn_e,
        "configuration reasoning", "multi-hop", "medium",
        "Multi-hop: variant maps to CSS class in Button.__init__ and referenced in DEFAULT_CSS block.")

    add("textual_cfg_06",
        "How does `App.SCREENS` class variable pre-register named screens for deferred use?",
        app_path, "App", app_e,
        "configuration reasoning", "single-hop", "easy",
        "Single-hop: SCREENS dict handling is in app.py.")

    add("textual_cfg_07",
        "How does `App.BINDINGS` configure global keyboard shortcuts and what format must each entry follow?",
        app_path, "App", app_e,
        "configuration reasoning", "single-hop", "medium",
        "Single-hop: BINDINGS class variable and resolution are in app.py.")

    add_file("textual_cfg_08",
        "How does the `features.py` module gate optional Textual features at runtime?",
        feat_path, "configuration reasoning", "single-hop", "easy",
        "Single-hop: feature flags and their evaluation logic are in features.py.")

    return entries


def main():
    print("Building benchmark (v2)...")
    entries = build_entries()

    # Serialize, removing Nones
    data = []
    for e in entries:
        d = asdict(e)
        d = {k: v for k, v in d.items() if v is not None}
        data.append(d)

    # Deduplicate by id
    seen = {}
    deduped = []
    for d in data:
        if d["id"] not in seen:
            seen[d["id"]] = True
            deduped.append(d)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(deduped, f, indent=2)

    print(f"Built {len(deduped)} benchmark entries -> {OUTPUT_PATH}")

    from collections import Counter
    caps = Counter(e["reasoning_capability"] for e in deduped)
    comps = Counter(e["retrieval_complexity"] for e in deduped)
    diffs = Counter(e["difficulty"] for e in deduped)
    print("\nCapability distribution:", dict(caps))
    print("Complexity distribution:", dict(comps))
    print("Difficulty distribution:", dict(diffs))


if __name__ == "__main__":
    main()
