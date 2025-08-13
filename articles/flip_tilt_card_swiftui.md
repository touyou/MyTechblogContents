---
title: "フリップして傾けるカードを SwiftUI で実装する"
emoji: "💳"
type: "tech" # tech: 技術記事 / idea: アイデア
topics: ["SwiftUI", "iOS", "アニメーション"]
published: true
---

フリップするカードはありますが、さらに傾けられるカードはあまり見かけないので記録として残しておきます。
GPT-5に頼んで実装しました。

## 実際のコード

```swift
import SwiftUI
import simd

struct TiltFlipCard<Front: View, Back: View>: View {
    var front: (_ normal: SIMD3<Float>) -> Front
    var back: (_ normal: SIMD3<Float>) -> Back

    @State private var tiltX: CGFloat = 0
    @State private var tiltY: CGFloat = 0
    @State private var isFlipped = false
    @GestureState private var drag = CGSize.zero

    private let responsiveness: CGFloat = 0.15
    private let tiltMax: CGFloat = 10

    var body: some View {
        let worldNormal = normalFromTilt(tiltXDeg: Float(tiltX), tiltYDeg: Float(tiltY))
        let frontNormal = worldNormal
        let backNormal = -worldNormal

        // flipの処理とtiltの処理を分けれるようにZStackを二重にする
        ZStack {
            ZStack {
                front(frontNormal)
                    .opacity(isFlipped ? 0 : 1)
                back(backNormal)
                    .rotation3DEffect(.degrees(180), axis: (x: 0, y: 1, z: 0))
                    .opacity(isFlipped ? 1 : 0)
            }
            .compositingGroup()
            // フリップする方のエフェクト
            .rotation3DEffect(.degrees(isFlipped ? 180 : 0), axis: (x: 0, y: 1, z: 0), perspective: 0.7)
            // Tap Gestureは設定場所によっては反応しないため注意
            .onTapGesture {
                withAnimation(.spring) {
                    isFlipped.toggle()
                }
            }
        }
        // 傾ける方のエフェクト
        .rotation3DEffect(.degrees(tiltX), axis: (x: 1, y: 0, z: 0))
        .rotation3DEffect(.degrees(tiltY), axis: (x: 0, y: 1, z: 0))
        .gesture(
            DragGesture(minimumDistance: 0)
                .updating($drag) { value, state, _ in
                    state = value.translation
                }
                .onEnded { _ in
                    withAnimation(.spring) {
                        tiltX = 0
                        tiltY = 0
                    }
                }
        )
        .onAppear {
            withAnimation {
                tiltY = 5
            } completion: {
                tiltY = 0
            }
        }
        // tiltの更新にはonChangeを使う
        .onChange(of: drag, initial: false) { _, newValue in
            tiltX = clampFloat(-newValue.height * responsiveness, -tiltMax, tiltMax)
            tiltY = clampFloat(newValue.width * responsiveness, -tiltMax, tiltMax)
        }
    }

    // 法線ベクトルが必要だったため、その計算
    private func normalFromTilt(tiltXDeg: Float, tiltYDeg: Float) -> SIMD3<Float> {
        let n0 = SIMD3<Float>(0, 0, 1)

        // それぞれのtiltに対する回転行列を計算
        let rx = rotationMatrix(axis: SIMD3<Float>(1, 0, 0), degrees: tiltXDeg)
        let ry = rotationMatrix(axis: SIMD3<Float>(0, 1, 0), degrees: tiltYDeg)

        let r = simd_mul(ry, rx)

        let v = simd_mul(r, SIMD4<Float>(n0, 0)).xyz
        return simd_normalize(v)
    }

    // 軸と角度から回転行列を計算する関数
    private func rotationMatrix(axis: SIMD3<Float>, degrees: Float) -> simd_float4x4 {
        let rad = degrees * .pi / 180
        let a = simd_normalize(axis)
        let c = cos(rad)
        let s = sin(rad)
        let t = 1 - c

        let m = simd_float3x3(
            SIMD3<Float>(t * a.x * a.x + c, t * a.x * a.y - s * a.z, t * a.x * a.z + s * a.y),
            SIMD3<Float>(t * a.x * a.y + s * a.z, t * a.y * a.y + c, t * a.y * a.z - s * a.x),
            SIMD3<Float>(t * a.x * a.z - s * a.y, t * a.y * a.z + s * a.x, t * a.z * a.z + c)
        )

        return simd_float4x4(
            SIMD4<Float>(m.columns.0, 0),
            SIMD4<Float>(m.columns.1, 0),
            SIMD4<Float>(m.columns.2, 0),
            SIMD4<Float>(0, 0, 0, 1))
    }

    // clampの実装
    private func clampFloat(_ v: CGFloat, _ lo: CGFloat, _ hi: CGFloat) -> CGFloat {
        min(max(v, lo), hi)
    }
}

extension SIMD4 where Scalar == Float {
    fileprivate var xyz: SIMD3<Float> {
        return SIMD3<Float>(x, y, z)
    }
}
```

なお法線ベクトルの計算する形にしているため、少し複雑になっていますが、単純にフリップと傾けるだけであればもう少しシンプルになるかと思います。

## おまけ：法線ベクトルの使い道

法線ベクトルに関しては、キラカードのシェーダーに利用していました。
three.jsのこちらの記事を参考にしています。

[キラカードシェーダーでポケカ再現！](https://note.com/sawa_zen/n/n77a7527c290e)

```cpp
#include <metal_stdlib>
#include <SwiftUI/SwiftUI_Metal.h>
using namespace metal;

#define ANGLE_STRENGTH 10.0
#define NOISE_SCALE 6.0

// NOTE: https://zenn.dev/ikeh1024/articles/cc51846dfad295#modとfmodの差異
template<typename Tx, typename Ty>
inline Tx mod(Tx x, Ty y)
{
    return x - y * floor(x / y);
}

// ref: https://github.com/sawa-zen/looking-glass-webxr-study/blob/main/src/HolographicMaterial/fragment.glsl

float generateRandomFloat(float2 st) {
    return fract(sin(dot(st.xy, float2(12.9898, 78.233))) * 43758.5453123);
}

float generateValueNoise(float2 st) {
    float2 i = floor(st);
    float2 f = fract(st);

    float a = generateRandomFloat(i);
    float b = generateRandomFloat(i + float2(1.0, 0.0));
    float c = generateRandomFloat(i + float2(0.0, 1.0));
    float d = generateRandomFloat(i + float2(1.0, 1.0));

    float2 u = f * f * (3.0 - 2.0 * f);

    return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
}

float3 hsv2rgb(float3 hsv) {
    float4 K = float4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
    float3 p = abs(fract(hsv.xxx + K.xyz) * 6.0 - K.www);
    return hsv.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), hsv.y);
}

float3 rgb2hsv(float3 rgb) {
    float4 K = float4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
    float4 p = mix(float4(rgb.bg, K.wz), float4(rgb.gb, K.xy), step(rgb.b, rgb.g));
    float4 q = mix(float4(p.xyw, rgb.r), float4(rgb.r, p.yzx), step(p.x, rgb.r));

    float d = q.x - min(q.w, q.y);
    float e = 1.0e-10;
    return float3(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
}

float getViewAngle(float3 normal) {
    float3 faceNormal = normalize(normal);
    float3 lightDir = normalize(float3(0.0, -1.0, -1.0));
    float angle = acos(dot(faceNormal, lightDir));
    return angle;
}

float3 generateAngleRGB(float strength, float3 normal) {
    float pi = M_PI_F;
    float angle = mod(getViewAngle(normal) * strength, pi) / pi;
    float3 colorHSV = float3(angle, 1.0, 1.0);
    return hsv2rgb(colorHSV);
}

float3 generateKiraRGB(float3 colorNoiseRGB, float3 normal) {
    float3 angleColorRGB = generateAngleRGB(ANGLE_STRENGTH, normal);
    float colorDiff = distance(colorNoiseRGB, angleColorRGB);
    float3 kiraNoiseHSV = rgb2hsv(colorNoiseRGB);
    kiraNoiseHSV.z = max(1.0 - colorDiff, 0.0);
    return hsv2rgb(kiraNoiseHSV);
}

[[ stitchable ]] half4 kiraEffect(float2 position, SwiftUI::Layer layer, float4 bounds, float3 normal, texture2d<half> monoTexture) {
    float2 fragCoord = float2(position.x, bounds.z - position.y);
    float2 uv = float2(fragCoord.x / bounds.z,
                      fragCoord.y / bounds.w);
    float2 UV = float2(position.x / bounds.z, position.y / bounds.w);

    float2 pos = float2(uv * NOISE_SCALE);
    float valueNoise = generateValueNoise(pos);
    float3 colorNoiseHSV = float3(valueNoise, 1.0, 1.0);
    float3 colorNoiseRGB = hsv2rgb(colorNoiseHSV);
    constexpr sampler imageSampler(address::clamp_to_edge,
                                   filter::nearest);
    float3 kiraNoiseRGB = generateKiraRGB(colorNoiseRGB, normal) * float3(monoTexture.sample(imageSampler, UV).rgb);
    return half4(half3(kiraNoiseRGB) + layer.sample(position).rgb, layer.sample(position).a);
}
```
