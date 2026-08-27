/**
 * Visualizador 3D.
 *
 * A única entrada é `isFlying`. Nenhum componente daqui para dentro conhece o
 * backend, o TanStack Query ou o formato da API — quem liga o estado real à
 * cena é a página, com uma linha:
 *
 *     <DroneViewer isFlying={status?.connected ?? false} />
 *
 * Isso mantém a cena testável isoladamente e permite reusá-la em qualquer
 * outra tela.
 */
import { Suspense } from "react";
import { Canvas } from "@react-three/fiber";
import { ContactShadows, Environment, OrbitControls } from "@react-three/drei";
import { Box, Flex, Text } from "@chakra-ui/react";
import { StatusDot } from "@/components/ui/StatusDot";
import { DroneModel } from "./DroneModel";
import { DronePlaceholder } from "./DronePlaceholder";

const HAS_MODEL = Boolean(import.meta.env.VITE_DRONE_MODEL_URL);

interface Props {
  isFlying: boolean;
  height?: string | number;
}

export function DroneViewer({ isFlying, height = "100%" }: Props) {
  return (
    <Box
      position="relative"
      height={height}
      minH="260px"
      rounded="card"
      overflow="hidden"
      bg="bg.viewer"
      borderWidth="1px"
      borderColor="border.subtle"
    >
      <Canvas
        shadows
        dpr={[1, 2]}
        camera={{ position: [2.6, 1.8, 3.2], fov: 42 }}
        // Sem stream, sem loop: economiza GPU em uma tela que fica aberta o dia todo.
        frameloop="always"
      >
        <color attach="background" args={["#0B1120"]} />
        <ambientLight intensity={0.55} />
        <directionalLight position={[4, 6, 3]} intensity={1.5} castShadow />
        <spotLight position={[-4, 5, -2]} intensity={0.6} color="#2FC4B8" />

        <Suspense fallback={<DronePlaceholder isFlying={isFlying} />}>
          {HAS_MODEL ? <DroneModel isFlying={isFlying} /> : <DronePlaceholder isFlying={isFlying} />}
        </Suspense>

        <ContactShadows
          position={[0, -0.62, 0]}
          opacity={isFlying ? 0.4 : 0.65}
          blur={isFlying ? 3.2 : 1.6}
          scale={7}
          far={3}
        />
        <Environment preset="city" />
        <OrbitControls
          enablePan={false}
          minPolarAngle={Math.PI / 6}
          maxPolarAngle={Math.PI / 2.1}
          minDistance={2.4}
          maxDistance={7}
          autoRotate={!isFlying}
          autoRotateSpeed={0.5}
        />
      </Canvas>

      <Flex
        position="absolute"
        left={4}
        bottom={4}
        align="center"
        gap={2}
        bg="blackAlpha.600"
        backdropFilter="blur(8px)"
        px={3}
        py={1.5}
        rounded="control"
      >
        <StatusDot tone={isFlying ? "live" : "idle"} />
        <Text textStyle="readout" fontSize="xs" color="white">
          {isFlying ? "EM VOO" : "EM SOLO"}
        </Text>
      </Flex>
    </Box>
  );
}
