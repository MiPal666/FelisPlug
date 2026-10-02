import QtQuick 2.0
import Sailfish.Silica 1.0
import "pages"
import "cover"

ApplicationWindow {
    id: appWindow

    allowedOrientations: defaultAllowedOrientations

    property string appVersion: "0.1.0"

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
