#include <gtk/gtk.h>
#include <gmodule.h>

/* gtklock v5 module ABI: first two fields of upstream include/window.h.
 * https://github.com/jovanlanik/gtklock/blob/v5.0.0/include/window.h
 * Those two fields match v4.0.0. Remaining private fields stay opaque.
 * A mismatched major version makes gtklock exit before it locks. */
struct Window { GdkMonitor *monitor; GtkWidget *window; };
struct GtkLock;
extern void gtklock_focus_window(struct GtkLock *, struct Window *);
G_MODULE_EXPORT const guint module_major_version = 5;
G_MODULE_EXPORT const guint module_minor_version = 0;

static void refresh_name(GdkScreen *screen, GtkWidget *window) {
    if (!gtk_widget_get_realized(window)) return;
    GdkMonitor *monitor = g_object_get_data(G_OBJECT(window), "yuru-monitor");
    GdkDisplay *display = gtk_widget_get_display(window);
    for (int i = 0; i < gdk_display_get_n_monitors(display); i++) {
        if (gdk_display_get_monitor(display, i) != monitor) continue;
        G_GNUC_BEGIN_IGNORE_DEPRECATIONS
        char *name = gdk_screen_get_monitor_plug_name(screen, i);
        G_GNUC_END_IGNORE_DEPRECATIONS
        if (name) {
            gtk_widget_set_name(window, name);
            const char *preferred = g_object_get_data(G_OBJECT(window), "yuru-preferred-output");
            if (preferred && g_str_equal(name, preferred))
                gtklock_focus_window(g_object_get_data(G_OBJECT(window), "yuru-lock-context"),
                                     g_object_get_data(G_OBJECT(window), "yuru-lock-window"));
            g_free(name);
        }
        break;
    }
}

static gboolean refresh_idle(gpointer data) {
    GtkWidget *window = data;
    if (!gtk_widget_in_destruction(window))
        refresh_name(gtk_widget_get_screen(window), window);
    return G_SOURCE_REMOVE;
}

G_MODULE_EXPORT void on_window_create(struct GtkLock *lock, struct Window *window) {
    GtkWidget *widget = window->window;
    /* This module accompanies the managed default gtklock/config.ini. */
    char *path = g_build_filename(g_get_user_config_dir(), "gtklock", "config.ini", NULL);
    GKeyFile *config = g_key_file_new();
    if (g_key_file_load_from_file(config, path, G_KEY_FILE_NONE, NULL)) {
        gsize count = 0;
        char **priority = g_key_file_get_string_list(config, "main", "monitor-priority", &count, NULL);
        if (priority && count)
            g_object_set_data_full(G_OBJECT(widget), "yuru-preferred-output",
                                   g_strdup(priority[0]), g_free);
        g_strfreev(priority);
    }
    g_key_file_unref(config);
    g_free(path);
    g_object_set_data(G_OBJECT(widget), "yuru-lock-context", lock);
    g_object_set_data(G_OBJECT(widget), "yuru-lock-window", window);
    gtk_style_context_add_class(gtk_widget_get_style_context(widget), "yuru-lock");
    g_object_set_data_full(G_OBJECT(widget), "yuru-monitor",
                          g_object_ref(window->monitor), g_object_unref);
    g_signal_connect_object(gtk_widget_get_screen(widget), "monitors-changed",
                            G_CALLBACK(refresh_name), widget, 0);
    g_idle_add_full(G_PRIORITY_DEFAULT_IDLE, refresh_idle,
                    g_object_ref(widget), g_object_unref);
}
