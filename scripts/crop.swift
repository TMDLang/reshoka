import Foundation
import CoreGraphics
import ImageIO

guard CommandLine.arguments.count >= 7 else {
    print("Usage: crop <input> <output> <x> <y> <w> <h>")
    exit(1)
}

let imagePath = CommandLine.arguments[1]
let outPath = CommandLine.arguments[2]
let x = CGFloat(Double(CommandLine.arguments[3])!)
let y = CGFloat(Double(CommandLine.arguments[4])!)
let w = CGFloat(Double(CommandLine.arguments[5])!)
let h = CGFloat(Double(CommandLine.arguments[6])!)

let url = URL(fileURLWithPath: imagePath) as CFURL
guard let source = CGImageSourceCreateWithURL(url, nil),
      let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
    print("Failed to load \(imagePath)")
    exit(1)
}

let rect = CGRect(x: x, y: y, width: w, height: h)
guard let cropped = image.cropping(to: rect) else {
    print("Failed to crop")
    exit(1)
}

let outUrl = URL(fileURLWithPath: outPath) as CFURL
guard let dest = CGImageDestinationCreateWithURL(outUrl, "public.jpeg" as CFString, 1, nil) else {
    print("Failed to create destination")
    exit(1)
}

CGImageDestinationAddImage(dest, cropped, nil)
CGImageDestinationFinalize(dest)
print("Successfully saved cropped image to \(outPath)")
