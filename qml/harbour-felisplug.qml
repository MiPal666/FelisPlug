import QtQuick 2.0
import Sailfish.Silica 1.0
import "pages"
import "cover"

ApplicationWindow {
    id: appWindow

    allowedOrientations: defaultAllowedOrientations

    property string appVersion: "0.2.0"

    // Refresh only when explicitly requested or when returning from the Cover.
    signal refreshRequested()
    property bool wasInBackground: false

    Connections {
        target: Qt.application
        onStateChanged: {
            if (Qt.application.state === Qt.ApplicationActive) {
                if (appWindow.wasInBackground) {
                    appWindow.wasInBackground = false
                    appWindow.refreshRequested()
                }
            } else {
                appWindow.wasInBackground = true
            }
        }
    }

    property int coverOnCount: 0
    property int coverOffCount: 0
    property int coverUnavailableCount: 0
    property int coverPlugCount: 0

    initialPage: Component {
        FirstPage {
            appWindowRef: appWindow
        }
    }

    cover: Component {
        CoverPage {
            appWindowRef: appWindow
        }
    }
}
