import Foundation
import CoreGraphics
import ImageIO

guard CommandLine.arguments.count >= 3 else {
    print("Usage: slice_score.swift <imagePath> <outputDir>")
    exit(1)
}

let imagePath = CommandLine.arguments[1]
let outputDir = CommandLine.arguments[2]
let fileManager = FileManager.default

try? fileManager.createDirectory(atPath: outputDir, withIntermediateDirectories: true, attributes: nil)

let url = URL(fileURLWithPath: imagePath) as CFURL
guard let src = CGImageSourceCreateWithURL(url, nil),
      let img = CGImageSourceCreateImageAtIndex(src, 0, nil) else {
    print("Error: Cannot load image \(imagePath)")
    exit(1)
}

let w = img.width
let h = img.height

let colorSpace = CGColorSpaceCreateDeviceGray()
var pixels = [UInt8](repeating: 0, count: w * h)
guard let ctx = CGContext(data: &pixels, width: w, height: h, bitsPerComponent: 8, bytesPerRow: w, space: colorSpace, bitmapInfo: CGImageAlphaInfo.none.rawValue) else {
    print("Error: Cannot create CGContext")
    exit(1)
}
ctx.draw(img, in: CGRect(x: 0, y: 0, width: w, height: h))

// 1. Calculate horizontal dark pixel density across middle 50%
let minX = Int(Double(w) * 0.25)
let maxX = Int(Double(w) * 0.75)
let widthSpan = maxX - minX

var rowDensities = [Double](repeating: 0, count: h)
for y in 0..<h {
    var darkCount = 0
    let rowStart = y * w
    for x in minX..<maxX {
        if pixels[rowStart + x] < 140 { darkCount += 1 }
    }
    rowDensities[y] = Double(darkCount) / Double(widthSpan)
}

var candidateLines = [Int]()
for y in 100..<(h - 100) {
    if rowDensities[y] > 0.22 {
        candidateLines.append(y)
    }
}

var lineCenters = [Int]()
if !candidateLines.isEmpty {
    var currentGroup = [candidateLines[0]]
    for i in 1..<candidateLines.count {
        if candidateLines[i] == candidateLines[i-1] + 1 {
            currentGroup.append(candidateLines[i])
        } else {
            lineCenters.append(currentGroup[currentGroup.count / 2])
            currentGroup = [candidateLines[i]]
        }
    }
    lineCenters.append(currentGroup[currentGroup.count / 2])
}

// 2. Identify 5-line staves
var staves = [ClosedRange<Int>]()
var i = 0
while i < lineCenters.count {
    var staffLines = [lineCenters[i]]
    var j = i + 1
    while j < lineCenters.count && staffLines.count < 5 {
        let gap = lineCenters[j] - staffLines.last!
        if gap >= 12 && gap <= 35 {
            staffLines.append(lineCenters[j])
        } else if gap > 35 {
            break
        }
        j += 1
    }
    if staffLines.count >= 4 {
        staves.append(staffLines.first!...staffLines.last!)
        i = j
    } else {
        i += 1
    }
}

print("Detected \(staves.count) staves in \(imagePath)")

func saveCrop(rect: CGRect, to path: String) {
    guard let cropped = img.cropping(to: rect) else { return }
    let destUrl = URL(fileURLWithPath: path) as CFURL
    guard let dest = CGImageDestinationCreateWithURL(destUrl, "public.jpeg" as CFString, 1, nil) else { return }
    CGImageDestinationAddImage(dest, cropped, nil)
    CGImageDestinationFinalize(dest)
}

let cropX: CGFloat = CGFloat(Double(w) * 0.04)
let cropW: CGFloat = CGFloat(Double(w) * 0.92)

if staves.isEmpty {
    print("Warning: No staves detected by projection. Using fallback slicing.")
    let numStaves = 4
    let staffH = CGFloat(Double(h) * 0.65 / Double(numStaves))
    let topY = CGFloat(Double(h) * 0.15)
    for idx in 0..<numStaves {
        let y = topY + CGFloat(idx) * staffH
        let rect = CGRect(x: cropX, y: max(0, y - 20), width: cropW, height: min(CGFloat(h) - y, staffH + 40))
        saveCrop(rect: rect, to: "\(outputDir)/staff_\(idx + 1).png")
    }
} else {
    for (idx, staff) in staves.enumerated() {
        let staffHeight = CGFloat(staff.upperBound - staff.lowerBound)
        
        // Next boundary or lyrics area
        let prevBound: CGFloat = (idx == 0) ? CGFloat(staff.lowerBound) - staffHeight * 2.5 : CGFloat(staves[idx - 1].upperBound)
        let nextBound: CGFloat = (idx == staves.count - 1) ? CGFloat(staff.upperBound) + staffHeight * 3.5 : CGFloat(staves[idx + 1].lowerBound)
        
        // Midpoints between staves with safety margins
        let yStart = max(0, (CGFloat(staff.lowerBound) + prevBound) / 2.0 - 20)
        let yEnd = min(CGFloat(h), (CGFloat(staff.upperBound) + nextBound) / 2.0 + 20)
        let rect = CGRect(x: cropX, y: yStart, width: cropW, height: yEnd - yStart)
        
        saveCrop(rect: rect, to: "\(outputDir)/staff_\(idx + 1).png")
        print("  [Staff \(idx + 1)] Y: \(Int(yStart))..\(Int(yEnd)) -> staff_\(idx + 1).png")
    }
}

// Bottom lyrics crop
if let lastStaff = staves.last {
    let lyricsY = CGFloat(lastStaff.upperBound) + CGFloat(lastStaff.upperBound - lastStaff.lowerBound) * 1.5
    if lyricsY < CGFloat(h) - 100 {
        let rect = CGRect(x: cropX, y: lyricsY, width: cropW, height: CGFloat(h) - lyricsY - 20)
        saveCrop(rect: rect, to: "\(outputDir)/bottom_lyrics.png")
        print("  [Bottom Lyrics] Y: \(Int(lyricsY))..\(h) -> bottom_lyrics.png")
    }
}
