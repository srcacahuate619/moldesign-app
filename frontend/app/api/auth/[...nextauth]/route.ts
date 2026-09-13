import NextAuth from "next-auth";
import GoogleProvider from "next-auth/providers/google";
import AzureADProvider from "next-auth/providers/azure-ad";

const handler = NextAuth({
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID || "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET || "",
    }),
  ],
  callbacks: {
    async jwt({ token, account }) {
      // Si account existe, es la primera vez que se hace login (cuando se recibe el token)
      if (account) {
        token.id_token = account.id_token;
        token.provider = account.provider;
      }
      return token;
    },
    async session({ session, token }) {
      // Inyectar el id_token y el provider en la sesión para que el frontend pueda enviarlo a FastAPI
      if (session.user) {
        // Los dos campos están declarados en `types/next-auth.d.ts`: antes se
        // escribían con `as any` y el tipo de `Session` no los mencionaba, así
        // que quien la leía no sabía que existían.
        session.id_token = token.id_token;
        session.provider = token.provider;
      }
      return session;
    },
  },
  session: {
    strategy: "jwt",
    maxAge: 30 * 60, // 30 minutos (suficiente para hacer el puente a FastAPI)
  },
  pages: {
    signIn: "/login",
    error: "/login", // Redirigir errores de OAuth al login
  },
});

export { handler as GET, handler as POST };
