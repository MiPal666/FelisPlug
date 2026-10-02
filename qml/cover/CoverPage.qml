import QtQuick 2.0
import Sailfish.Silica 1.0

CoverBackground {
    id: coverRoot

    property var appWindowRef

    readonly property int onCount: appWindowRef ? appWindowRef.coverOnCount : 0
    readonly property int offCount: appWindowRef ? appWindowRef.coverOffCount : 0
    readonly property int unavailableCount: appWindowRef ? appWindowRef.coverUnavailableCount : 0
    readonly property int totalCount: appWindowRef ? appWindowRef.coverPlugCount : 0

    Column {
        anchors {
            fill: parent
            margins: Theme.paddingLarge
        }
        spacing: Theme.paddingMedium

        Label {
            width: parent.width
            text: "Felis Plug"
            truncationMode: TruncationMode.Fade
            horizontalAlignment: Text.AlignHCenter
            color: Theme.highlightColor
            font.pixelSize: Theme.fontSizeLarge
        }

        Label {
            width: parent.width
            text: qsTr("EZVIZ smart plugs")
            horizontalAlignment: Text.AlignHCenter
            color: Theme.secondaryColor
            font.pixelSize: Theme.fontSizeSmall
        }

        Item { width: 1; height: Theme.paddingLarge }

        Row {
            width: parent.width
            spacing: Theme.paddingLarge

            Item {
                width: (parent.width - parent.spacing) / 2
                height: onColumn.height + Theme.paddingLarge

                Rectangle {
                    anchors.fill: parent
                    radius: Theme.paddingMedium
                    color: "#18263a"
                    opacity: 0.95
                }

                Column {
                    id: onColumn
                    width: parent.width
                    anchors.centerIn: parent
                    spacing: Theme.paddingSmall

                    Label {
                        width: parent.width
                        text: qsTr("On")
                        horizontalAlignment: Text.AlignHCenter
                        color: Theme.primaryColor
                        font.pixelSize: Theme.fontSizeSmall
                    }

                    Label {
                        width: parent.width
                        text: onCount
                        horizontalAlignment: Text.AlignHCenter
                        color: "#38d67a"
                        font.pixelSize: Theme.fontSizeHuge
                    }
                }
            }

            Item {
                width: (parent.width - parent.spacing) / 2
                height: offColumn.height + Theme.paddingLarge

                Rectangle {
                    anchors.fill: parent
                    radius: Theme.paddingMedium
                    color: "#18263a"
                    opacity: 0.95
                }

                Column {
                    id: offColumn
                    width: parent.width
                    anchors.centerIn: parent
                    spacing: Theme.paddingSmall

                    Label {
                        width: parent.width
                        text: qsTr("Off")
                        horizontalAlignment: Text.AlignHCenter
                        color: Theme.primaryColor
                        font.pixelSize: Theme.fontSizeSmall
                    }

                    Label {
                        width: parent.width
                        text: offCount
                        horizontalAlignment: Text.AlignHCenter
                        color: Theme.secondaryHighlightColor
                        font.pixelSize: Theme.fontSizeHuge
                    }
                }
            }
        }

        Item { width: 1; height: Theme.paddingMedium }

        Label {
            width: parent.width
            text: qsTr("Unavailable: %1").arg(unavailableCount)
            horizontalAlignment: Text.AlignHCenter
            color: unavailableCount > 0 ? Theme.highlightColor : Theme.secondaryColor
            font.pixelSize: Theme.fontSizeSmall
        }

        Label {
            width: parent.width
            text: qsTr("Total plugs: %1").arg(totalCount)
            horizontalAlignment: Text.AlignHCenter
            color: Theme.secondaryColor
            font.pixelSize: Theme.fontSizeSmall
        }
    }
}
