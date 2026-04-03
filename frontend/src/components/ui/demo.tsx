import { SignInPage } from "@/components/ui/sign-in-flow-1";

const DemoOne = () => {
  return (
    <div className="flex w-full h-screen justify-center items-center">
      <SignInPage />
    </div>
  );
};

export { DemoOne };
import { HeroGeometric } from "@/components/ui/shape-landing-hero";

function DemoHeroGeometric() {
  return (
    <HeroGeometric
      badge="Kokonut UI"
      title1="Elevate Your"
      title2="Digital Vision"
    />
  );
}

export { DemoHeroGeometric };
