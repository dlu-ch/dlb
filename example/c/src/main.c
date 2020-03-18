/**
 * @file
 * The one and only.
 */

#include <stdio.h>
#include <gtk/gtk.h>
#include "Generated/Version.h"


static void activate(GtkApplication *app, gpointer user_data) {
    GtkWidget *const window = gtk_application_window_new(app);
    gtk_window_set_title (GTK_WINDOW(window), "Application " APPLICATION_VERSION);
    gtk_window_set_default_size(GTK_WINDOW (window), 200, 200);
    gtk_widget_show_all(window);
}


/**
 * Show the application's version.
 *
 * @return 0
 */
int main(int argc, char **const argv) {
    GtkApplication *const app = gtk_application_new("org.gtk.example", G_APPLICATION_FLAGS_NONE);

    g_signal_connect(app, "activate", G_CALLBACK(activate), NULL);
    int status = g_application_run(G_APPLICATION(app), argc, argv);
    g_object_unref(app);

    return status;
}
