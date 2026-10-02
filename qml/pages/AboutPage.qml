import QtQuick 2.0
import Sailfish.Silica 1.0

Page {
    id: page

    property string appVersion: "0.1.0"

    allowedOrientations: Orientation.All

    SilicaFlickable {
        anchors.fill: parent
        contentHeight: aboutColumn.height + Theme.paddingLarge

        VerticalScrollDecorator {}

        Column {
            id: aboutColumn
            width: parent.width
            spacing: Theme.paddingLarge

            PageHeader {
                title: qsTr("About")
            }

            Label {
                width: parent.width - 2 * Theme.horizontalPageMargin
                x: Theme.horizontalPageMargin
                text: qsTr("Felis Plug for EZVIZ")
                wrapMode: Text.Wrap
                horizontalAlignment: Text.AlignHCenter
                color: Theme.highlightColor
                font.pixelSize: Theme.fontSizeLarge
            }

            Label {
                width: parent.width - 2 * Theme.horizontalPageMargin
                x: Theme.horizontalPageMargin
                text: qsTr("Version %1").arg(appVersion)
                horizontalAlignment: Text.AlignHCenter
                color: Theme.secondaryColor
            }

            SectionHeader {
                text: qsTr("About the application")
            }

            Label {
                width: parent.width - 2 * Theme.horizontalPageMargin
                x: Theme.horizontalPageMargin
                text: qsTr("Unofficial Sailfish OS client for controlling EZVIZ smart plugs through the EZVIZ consumer cloud.")
                wrapMode: Text.Wrap
                color: Theme.primaryColor
            }

            Label {
                width: parent.width - 2 * Theme.horizontalPageMargin
                x: Theme.horizontalPageMargin
                text: qsTr("This application is not affiliated with, endorsed by, or sponsored by EZVIZ or Hikvision.")
                wrapMode: Text.Wrap
                color: Theme.secondaryColor
                font.pixelSize: Theme.fontSizeSmall
            }

            Label {
                width: parent.width - 2 * Theme.horizontalPageMargin
                x: Theme.horizontalPageMargin
                text: qsTr("Your EZVIZ password is never stored. Only the session token is kept locally for subsequent launches.")
                wrapMode: Text.Wrap
                color: Theme.secondaryColor
                font.pixelSize: Theme.fontSizeSmall
            }
        }
    }
}
